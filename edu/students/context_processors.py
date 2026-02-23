from .services import get_overall_progress, get_top_modules_by_time

def global_progress(request):
    user = request.user
    if user.is_authenticated:
        return {
            "overall_progress": get_overall_progress(user),
            "top_modules": get_top_modules_by_time(user, limit=3),
        }
    return {
        "overall_progress": 0,
        "top_modules": [],
    }
