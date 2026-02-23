from django.db.models import Sum
from courses.models import Course, Module
from .models import ModuleProgress
import time
import redis
from django.conf import settings

ONLINE_USERS_KEY = "presence:online_users"
ONLINE_WINDOW_SECONDS = 120  # user is "online" if active in last 120s

_presence_redis = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
)

def touch_user_presence(user_id: int, window_seconds: int = ONLINE_WINDOW_SECONDS) -> int:
    now = int(time.time())
    cutoff = now - window_seconds
    member = str(user_id)
    
    try:
        pipe = _presence_redis.pipeline()
        pipe.zadd(ONLINE_USERS_KEY, {member: now})          # upsert heartbeat
        pipe.zremrangebyscore(ONLINE_USERS_KEY, 0, cutoff)  # remove stale
        pipe.zcard(ONLINE_USERS_KEY)                        # count online
        pipe.expire(ONLINE_USERS_KEY, window_seconds * 2)   # safety TTL
        _, _, online_count, _ = pipe.execute()
        return int(online_count)
    
    except redis.RedisError:
        return 0
    
def mark_module_completed(user, module):
    progress, created = ModuleProgress.objects.get_or_create(
        user=user,
        module=module,
        course=module.course
    )
    progress.completed = True
    progress.save()


def add_time_spent(user, module, seconds):
    progress, _ = ModuleProgress.objects.get_or_create(
        user=user,
        module=module,
        course=module.course,
        defaults={"completed": False, "time_spent": 0} # Ensure default is 0
    )

    # Django F() expressions are safer for concurrent updates to prevent race conditions
    from django.db.models import F
    progress.time_spent = F('time_spent') + seconds
    progress.save(update_fields=["time_spent"])
    
    
def get_course_time_spent(user, course):
    result = ModuleProgress.objects.filter(
        user=user,
        course=course
    ).aggregate(total=Sum('time_spent'))

    return result['total'] or 0


def get_overall_progress(user):
    courses = user.courses_joined.all()

    total_modules = Module.objects.filter(course__in=courses).count()

    if total_modules == 0:
        return 0

    completed_modules = ModuleProgress.objects.filter(
        user=user,
        completed=True,
        course__in=courses
    ).count()

    return round((completed_modules / total_modules) * 100, 2)

# Top 3 courses

def get_top_courses_by_time(user, limit=3):
    return list(
        ModuleProgress.objects
        .filter(user_id=user.id, time_spent__gt=0, course__students=user)
        .values("course_id", "course__title")
        .annotate(total_time=Sum("time_spent"))
        .order_by("-total_time")[:limit]
    )