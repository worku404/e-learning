# URL pattern helper.
from django.urls import path
from .views import TrackTimeView, MarkModuleCompleteView
# Student app views used by these routes.
from . import views

urlpatterns = [
    path(
        "courses/",
        # Enrolled courses list for current user.
        # Must not be shared-cached; data is user-specific.
        views.StudentCourseListView.as_view(),
        name="student_course_list",
    ),
    path(
        "course/<pk>/",
        # Course detail default view (first module).
        # Must not be shared-cached; access depends on current user enrollment.
        views.StudentCourseDetailView.as_view(),
        name="student_course_detail",
    ),
    path(
        "course/<pk>/<int:module_id>/",
        # Course detail with a specific module selected.
        # Must not be shared-cached; access depends on current user enrollment.
        views.StudentCourseDetailView.as_view(),
        name="student_course_detail_module",
    ),
    path(
        "register/",
        # User registration (not cached).
        views.StudentRegistrationView.as_view(),
        name="student_registration",
    ),
    path(
        "enroll-course/",
        # POST enrollment endpoint (not cached).
        views.StudentEnrollCourseView.as_view(),
        name="student_enroll_course",
    ),
    path('module/<int:module_id>/track-time/',
         TrackTimeView.as_view(),
         name='track_time'),
    path(
        "file/<int:file_id>/download/",
        views.DownloadModuleFileView.as_view(),
        name="student_file_download",
    ),
    path(
        "image/<int:image_id>/",
        views.ModuleImageView.as_view(),
        name="student_module_image",
    ),
    path(
        'module/<int:module_id>/complete/',
        MarkModuleCompleteView.as_view(),
        name='mark_module_complete',
    ),
    path(
    "file/<int:file_id>/view/",
    views.ModuleFilePreviewView.as_view(),
    name="student_file_view",
),

]
