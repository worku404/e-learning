from .services import get_overall_progress

def global_progress(request):
    if request.user.is_authenticated:
        return {
            "overall_progress": get_overall_progress(request.user)
        }
    return {"overall_progress": 0}