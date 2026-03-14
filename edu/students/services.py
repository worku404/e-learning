import time
from functools import lru_cache

import redis
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import F, Sum
from django.utils import timezone

from courses.models import Content, Course, File, Module, Text
from .models import ContentProgress, CourseProgress, ModuleProgress

ONLINE_USERS_KEY = "presence:online_users"
ONLINE_WINDOW_SECONDS = 120  # user is "online" if active in last 120s
CONTENT_COMPLETION_THRESHOLD = 95.0

_presence_redis = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
)


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


@lru_cache(maxsize=2)
def _content_type_id(model_cls):
    return ContentType.objects.get_for_model(model_cls).id


def touch_user_presence(user_id: int, window_seconds: int = ONLINE_WINDOW_SECONDS) -> int:
    now = int(time.time())
    cutoff = now - window_seconds
    member = str(user_id)

    try:
        pipe = _presence_redis.pipeline()
        pipe.zadd(ONLINE_USERS_KEY, {member: now})  # upsert heartbeat
        pipe.zremrangebyscore(ONLINE_USERS_KEY, 0, cutoff)  # remove stale
        pipe.zcard(ONLINE_USERS_KEY)  # count online
        pipe.expire(ONLINE_USERS_KEY, window_seconds * 2)  # safety TTL
        _, _, online_count, _ = pipe.execute()
        return int(online_count)
    except redis.RedisError:
        return 0


def _trackable_content_ids_for_module(module: Module) -> list[int]:
    text_ct = _content_type_id(Text)
    file_ct = _content_type_id(File)

    text_ids = list(
        Content.objects.filter(module=module, content_type_id=text_ct).values_list("id", flat=True)
    )

    file_contents = Content.objects.filter(module=module, content_type_id=file_ct)
    file_ids = list(file_contents.values_list("object_id", flat=True))
    pdf_file_ids = set(
        File.objects.filter(id__in=file_ids, file__iendswith=".pdf").values_list("id", flat=True)
    )
    pdf_content_ids = list(file_contents.filter(object_id__in=pdf_file_ids).values_list("id", flat=True))
    return text_ids + pdf_content_ids


def recompute_module_progress(user, module: Module) -> ModuleProgress:
    progress, _ = ModuleProgress.objects.get_or_create(
        user=user,
        module=module,
        course=module.course,
        defaults={"completed": False, "progress_percent": 0.0, "time_spent": 0},
    )

    trackable_ids = _trackable_content_ids_for_module(module)
    if not trackable_ids:
        return progress

    total = len(trackable_ids)
    sum_progress = (
        ContentProgress.objects.filter(user=user, content_id__in=trackable_ids)
        .aggregate(total=Sum("progress_percent"))
        .get("total")
        or 0.0
    )
    module_percent = _clamp_percent(sum_progress / total)
    progress.progress_percent = module_percent
    progress.completed = module_percent >= CONTENT_COMPLETION_THRESHOLD
    progress.save(update_fields=["progress_percent", "completed", "last_accessed"])
    return progress


def recompute_course_progress(user, course: Course) -> CourseProgress:
    """
    Recalculate and persist course-level progress for a single user.

    The course percentage is the average of module percentages.
    Course completion is stricter: every module must be completed.
    """
    total_modules = Module.objects.filter(course=course).count()
    sum_progress = (
        ModuleProgress.objects.filter(user=user, course=course)
        .aggregate(total=Sum("progress_percent"))
        .get("total")
        or 0.0
    )
    course_percent = 0.0
    if total_modules > 0:
        course_percent = round(_clamp_percent(sum_progress / total_modules), 2)

    completed_modules = (
        ModuleProgress.objects.filter(user=user, course=course, completed=True)
        .values("module_id")
        .distinct()
        .count()
    )
    course_completed = total_modules > 0 and completed_modules >= total_modules

    course_progress, _ = CourseProgress.objects.get_or_create(
        user=user,
        course=course,
        defaults={
            "progress_percent": course_percent,
            "completed": course_completed,
            "completed_at": timezone.now() if course_completed else None,
        },
    )

    # Keep these fields synchronized whenever module/content progress changes.
    course_progress.progress_percent = course_percent
    course_progress.completed = course_completed
    if course_completed and not course_progress.completed_at:
        course_progress.completed_at = timezone.now()
    if not course_completed and course_progress.completed_at:
        course_progress.completed_at = None
    course_progress.save(update_fields=["progress_percent", "completed", "completed_at", "last_accessed"])
    return course_progress


def get_or_recompute_course_progress(user, course: Course) -> CourseProgress:
    """
    Read the persisted row when available; otherwise compute and persist it.
    """
    existing = CourseProgress.objects.filter(user=user, course=course).first()
    if existing is not None:
        return existing
    return recompute_course_progress(user, course)


def get_course_progress_percent(user, course: Course) -> float:
    """
    Compatibility helper retained for existing template/context code.
    """
    return get_or_recompute_course_progress(user, course).progress_percent


def mark_module_completed(user, module):
    progress, _ = ModuleProgress.objects.get_or_create(
        user=user,
        module=module,
        course=module.course,
        defaults={"time_spent": 0},
    )
    progress.completed = True
    progress.progress_percent = 100.0
    progress.save(update_fields=["completed", "progress_percent", "last_accessed"])
    course_progress = recompute_course_progress(user, module.course)
    return progress, course_progress


def update_content_progress(user, content, kind: str, payload: dict, seconds_delta: int = 0) -> dict:
    kind = (kind or "").lower().strip()
    if kind not in {ContentProgress.CONTENT_KIND_TEXT, ContentProgress.CONTENT_KIND_PDF}:
        raise ValueError("Unsupported content kind")

    progress, _ = ContentProgress.objects.get_or_create(
        user=user,
        content=content,
        course=content.module.course,
        module=content.module,
        defaults={
            "content_type": kind,
            "progress_percent": 0.0,
            "completed": False,
            "seconds_spent": 0,
            "last_position": {},
        },
    )

    last_position = progress.last_position or {}
    next_percent = progress.progress_percent
    next_position = dict(last_position)

    if kind == ContentProgress.CONTENT_KIND_PDF:
        total_pages = max(1, int(payload.get("total_pages") or 1))
        current_page = max(1, min(int(payload.get("current_page") or 1), total_pages))
        incoming_max = int(payload.get("max_page_seen") or current_page)
        previous_max = int(last_position.get("max_page_seen") or 0)
        max_seen = max(previous_max, incoming_max, current_page)
        max_seen = max(1, min(max_seen, total_pages))

        pdf_percent = _clamp_percent((max_seen / total_pages) * 100.0)
        next_percent = max(progress.progress_percent, pdf_percent)
        next_position = {
            "current_page": current_page,
            "total_pages": total_pages,
            "max_page_seen": max_seen,
        }
        completed = max_seen >= total_pages and next_percent >= CONTENT_COMPLETION_THRESHOLD
    else:
        incoming_percent = _clamp_percent(float(payload.get("percent") or 0.0))
        next_percent = max(progress.progress_percent, incoming_percent)
        next_position = {"percent": round(next_percent, 2)}
        completed = next_percent >= CONTENT_COMPLETION_THRESHOLD

    seconds_delta = max(0, int(seconds_delta or 0))
    progress.content_type = kind
    progress.progress_percent = next_percent
    progress.completed = progress.completed or completed
    progress.last_position = next_position
    progress.seconds_spent = F("seconds_spent") + seconds_delta
    progress.save(
        update_fields=[
            "content_type",
            "progress_percent",
            "completed",
            "last_position",
            "seconds_spent",
            "updated",
        ]
    )
    progress.refresh_from_db()

    module_progress = recompute_module_progress(user, content.module)
    course_progress = recompute_course_progress(user, content.module.course)
    overall_progress = get_overall_progress(user)

    return {
        "content_progress": progress,
        "module_progress": module_progress,
        "course_progress": course_progress,
        "course_progress_percent": course_progress.progress_percent,
        "overall_progress_percent": overall_progress,
    }


def add_time_spent(user, module, seconds):
    progress, _ = ModuleProgress.objects.get_or_create(
        user=user,
        module=module,
        course=module.course,
        defaults={"completed": False, "progress_percent": 0.0, "time_spent": 0},
    )
    progress.time_spent = F("time_spent") + seconds
    progress.save(update_fields=["time_spent"])


def get_course_time_spent(user, course):
    result = ModuleProgress.objects.filter(
        user=user,
        course=course,
    ).aggregate(total=Sum("time_spent"))

    return result["total"] or 0


def get_overall_progress(user):
    courses = user.courses_joined.all()

    total_modules = Module.objects.filter(course__in=courses).count()
    if total_modules == 0:
        return 0.0

    accumulated = (
        ModuleProgress.objects.filter(user=user, course__in=courses)
        .aggregate(total=Sum("progress_percent"))
        .get("total")
        or 0.0
    )
    return round(_clamp_percent(accumulated / total_modules), 2)


def get_top_courses_by_time(user, limit=3):
    return list(
        ModuleProgress.objects.filter(user_id=user.id, time_spent__gt=0, course__students=user)
        .values("course_id", "course__title")
        .annotate(total_time=Sum("time_spent"))
        .order_by("-total_time")[:limit]
    )
