from django.db.models import Sum
from courses.models import Course, Module
from .models import ModuleProgress


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