"""
Student-facing views:
- account registration
- course enrollment
- enrolled course list/detail
"""


# URL builder used for redirects after successful actions.
import json
import os
import mimetypes
import subprocess
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.contrib.contenttypes.models import ContentType
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.cache import patch_response_headers

# Auth helpers and login-protection mixin.
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm

# Generic class-based views for create/form/list/detail pages.
from django.views.generic.edit import CreateView, FormView
from django.views.generic.list import ListView
from django.views.generic import TemplateView, DetailView, View


# Local enrollment form and Course model.
from .forms import CourseEnrollForm
from courses.models import Content, Course, File, Image, Module
from .models import ContentProgress, CourseProgress, ModuleProgress
from .services import (add_time_spent, mark_module_completed, 
                       get_overall_progress, get_course_time_spent,
                        touch_user_presence, update_content_progress,
                        recompute_course_progress
                    )


import redis


r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
)


def _course_progress_table_ready() -> bool:
    """
    Guard against runtime crashes when code is deployed before migrations run.

    Why this exists:
    - New code reads from CourseProgress.
    - If migration 0003 is not applied yet, querying that model raises:
      `ProgrammingError: relation "students_courseprogress" does not exist`.
    - This check lets pages render with a safe fallback until migrations are applied.
    """
    try:
        return CourseProgress._meta.db_table in connection.introspection.table_names()
    except (ProgrammingError, OperationalError):
        return False



class StudentRegistrationView(CreateView):
    # Registration page template.
    template_name = "students/student/registration.html"

    # Built-in Django user registration form (username + password1/password2).
    form_class = UserCreationForm

    # After successful registration/login, go to enrolled courses page.
    success_url = reverse_lazy("student_course_list")

    def form_valid(self, form):
        # 1) Save the new user via CreateView.
        response = super().form_valid(form)

        # 2) Read validated form data.
        cd = form.cleaned_data

        # 3) Authenticate using submitted credentials.
        user = authenticate(username=cd["username"], password=cd["password1"])

        # 4) Log in user in same request cycle.
        if user is not None:
            login(self.request, user)

        # 5) Continue normal redirect flow.
        return response


class StudentEnrollCourseView(LoginRequiredMixin, FormView):
    # This form sends a selected Course object (hidden input).
    form_class = CourseEnrollForm

    # Temporary storage: filled in form_valid(), used by get_success_url().
    course = None

    def form_valid(self, form):
        # 1) Pull validated Course object from form.
        self.course = form.cleaned_data["course"]

        # 2) Add current user to course.students (ManyToMany relation).
        self.course.students.add(self.request.user)

        # 3) Continue FormView success flow.
        return super().form_valid(form)

    def get_success_url(self):
        # Redirect to detail page of the enrolled course.
        return reverse_lazy("student_course_detail", args=[self.course.id])


class StudentCourseListView(LoginRequiredMixin, ListView):
    # Base model for list.
    model = Course
    template_name = "students/course/list.html"
    context_object_name = "courses"

    def get_queryset(self):
        # Return only courses where current user is enrolled.
        qs = super().get_queryset()
        return qs.filter(students__in=[self.request.user])

    def get_context_data(self, **kwargs):
        """
        Attach persisted course progress fields to each course card.
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user
        courses = list(context["courses"])

        # Defensive fallback for environments where DB migration 0003 is pending.
        if not _course_progress_table_ready():
            for course in courses:
                course.student_progress_percent = 0.0
                course.student_completed = False
            context["courses"] = courses
            return context

        try:
            progress_rows = {
                row.course_id: row
                for row in CourseProgress.objects.filter(user=user, course__in=courses)
            }
        except (ProgrammingError, OperationalError):
            # If schema and code become temporarily out of sync, keep page usable.
            progress_rows = {}

        for course in courses:
            row = progress_rows.get(course.id)
            if row is None:
                try:
                    row = recompute_course_progress(user, course)
                except (ProgrammingError, OperationalError):
                    row = None
            if row is None:
                course.student_progress_percent = 0.0
                course.student_completed = False
                continue
            course.student_progress_percent = round(row.progress_percent, 2)
            course.student_completed = row.completed

        context["courses"] = courses
        return context

class StudentCourseDetailView(LoginRequiredMixin, DetailView):
    model = Course
    template_name = "students/course/detail.html"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(students__in=[self.request.user])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        modules = list(course.modules.all())
        user = self.request.user

        if "module_id" in self.kwargs:
            module = get_object_or_404(Module, id=self.kwargs["module_id"], course=course)
        else:
            module = modules[0] if modules else None

        # Load and attach per-module progress rows so the template can render module percentages.
        module_progress_rows = {
            row.module_id: row
            for row in ModuleProgress.objects.filter(user=user, course=course)
        }
        for module_item in modules:
            module_row = module_progress_rows.get(module_item.id)
            module_item.student_progress_percent = round(
                module_row.progress_percent if module_row else 0.0,
                2,
            )
            module_item.student_completed = bool(module_row.completed) if module_row else False

        # Persisted course completion/percentage row (created on demand if missing).
        course_progress = None
        if _course_progress_table_ready():
            try:
                course_progress = CourseProgress.objects.filter(user=user, course=course).first()
                if course_progress is None:
                    course_progress = recompute_course_progress(user, course)
            except (ProgrammingError, OperationalError):
                course_progress = None

        if course_progress is None:
            # Fallback when CourseProgress table is unavailable:
            # derive a temporary course percentage from existing module rows.
            total_modules = len(modules)
            accumulated_percent = 0.0
            completed_modules = 0
            for module_item in modules:
                module_row = module_progress_rows.get(module_item.id)
                if not module_row:
                    continue
                accumulated_percent += float(module_row.progress_percent or 0.0)
                if module_row.completed:
                    completed_modules += 1

            fallback_percent = 0.0
            fallback_completed = False
            if total_modules > 0:
                fallback_percent = max(0.0, min(100.0, accumulated_percent / total_modules))
                fallback_completed = completed_modules >= total_modules

            course_progress = SimpleNamespace(
                progress_percent=round(fallback_percent, 2),
                completed=fallback_completed,
            )

        # Build a concrete list of module contents, and attach content progress state.
        module_contents = list(module.contents.select_related("content_type")) if module else []
        content_progress_rows = {
            row.content_id: row
            for row in ContentProgress.objects.filter(
                user=user,
                content__in=module_contents,
            )
        }
        for content_item in module_contents:
            progress_row = content_progress_rows.get(content_item.id)
            content_item.student_progress_percent = round(
                progress_row.progress_percent if progress_row else 0.0,
                2,
            )
            content_item.student_completed = bool(progress_row.completed) if progress_row else False
            # For PDF resume support we expose the stored JSON position to the template.
            content_item.student_last_position = progress_row.last_position if progress_row else {}

        context["module"] = module
        context["modules"] = modules
        context["module_contents"] = module_contents
        context["course_time"] = get_course_time_spent(self.request.user, course)
        context["course_progress"] = course_progress
        context["course_progress_percent"] = round(course_progress.progress_percent, 2)
        context["course_completed"] = course_progress.completed
        return context


class MarkModuleCompleteView(LoginRequiredMixin, View):
    def post(self, request, module_id):
        module = get_object_or_404(
            Module, 
            id=module_id,
            course__students=request.user,
            )

        module_progress, course_progress = mark_module_completed(request.user, module)

        return JsonResponse(
            {
                "status": "completed",
                "module_progress": {
                    "module_id": module.id,
                    "progress_percent": round(module_progress.progress_percent, 2),
                    "completed": module_progress.completed,
                },
                "course_progress": {
                    "course_id": module.course_id,
                    "progress_percent": round(course_progress.progress_percent, 2),
                    "completed": course_progress.completed,
                    "completed_at": (
                        course_progress.completed_at.isoformat()
                        if course_progress.completed_at
                        else None
                    ),
                },
            }
        )

class TrackTimeView(LoginRequiredMixin, View):
    def post(self, request, module_id):
        module = get_object_or_404(
            Module,
            id=module_id,
            course__students=request.user,
            
            )
        
        try:
            # Handle both standard POST and JSON/Beacon payloads
            seconds = int(request.POST.get('seconds', 0))
            
            if seconds > 0:
                add_time_spent(request.user, module, seconds)
                return JsonResponse({'status': 'tracked', 'seconds': seconds})
            
            return JsonResponse({'status': 'ignored', 'reason': '0 seconds'})
            
        except ValueError:
            return JsonResponse({'status': 'error', 'reason': 'Invalid seconds value'}, status=400)


class TrackContentProgressView(LoginRequiredMixin, View):
    def post(self, request, content_id):
        content = get_object_or_404(
            Content,
            id=content_id,
            module__course__students=request.user,
        )

        payload = {}
        if request.content_type and request.content_type.startswith("application/json"):
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                return JsonResponse(
                    {"status": "error", "reason": "Invalid JSON payload"},
                    status=400,
                )
        else:
            payload = request.POST.dict()

        kind = (payload.get("kind") or "").strip().lower()
        if not kind:
            model_name = content.content_type.model
            if model_name == "text":
                kind = "text"
            elif model_name == "file":
                file_obj = content.item
                filename = str(getattr(file_obj, "file", "") or "")
                if filename.lower().endswith(".pdf"):
                    kind = "pdf"

        try:
            seconds_delta = int(payload.get("seconds_delta", 0))
        except (TypeError, ValueError):
            seconds_delta = 0

        try:
            result = update_content_progress(
                user=request.user,
                content=content,
                kind=kind,
                payload=payload,
                seconds_delta=seconds_delta,
            )
        except ValueError as exc:
            return JsonResponse({"status": "error", "reason": str(exc)}, status=400)

        content_progress = result["content_progress"]
        module_progress = result["module_progress"]
        course = content.module.course
        course_progress = result["course_progress"]

        return JsonResponse(
            {
                "status": "tracked",
                "content_progress": {
                    "id": content_progress.id,
                    "content_id": content.id,
                    "kind": content_progress.content_type,
                    "progress_percent": round(content_progress.progress_percent, 2),
                    "completed": content_progress.completed,
                    "seconds_spent": content_progress.seconds_spent,
                    "last_position": content_progress.last_position,
                },
                "module_progress": {
                    "module_id": module_progress.module_id,
                    "progress_percent": round(module_progress.progress_percent, 2),
                    "completed": module_progress.completed,
                },
                "course_progress": {
                    "course_id": course.id,
                    "progress_percent": result["course_progress_percent"],
                    "completed": course_progress.completed,
                    "completed_at": (
                        course_progress.completed_at.isoformat()
                        if course_progress.completed_at
                        else None
                    ),
                },
                "overall_progress": result["overall_progress_percent"],
                "completed_flags": {
                    "content": content_progress.completed,
                    "module": module_progress.completed,
                    "course": course_progress.completed,
                },
            }
        )


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'students/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['overall_progress'] = get_overall_progress(user)
        context['courses'] = user.courses_joined.all()

        return context


class DownloadModuleFileView(LoginRequiredMixin, View):
    """
    Serves a module file as an attachment for enrolled users.
    This avoids relying on direct /media URLs in production.
    """
    def get(self, request, file_id):
        file_type = ContentType.objects.get_for_model(File)
        content = get_object_or_404(
            Content,
            content_type=file_type,
            object_id=file_id,
            module__course__students=request.user,
        )
        file_obj = content.item

        if not file_obj or not file_obj.file:
            raise Http404("File not found.")

        filename = os.path.basename(file_obj.file.name)

        try:
            return FileResponse(
                file_obj.file.open("rb"),
                as_attachment=True,
                filename=filename,
            )
        except FileNotFoundError as exc:
            raise Http404("File not found.") from exc




class ModuleImageView(LoginRequiredMixin, View):
    """
    Serves module images only to enrolled users.
    This avoids relying on direct /media URLs in production.
    """
    def get(self, request, image_id):
        image_type = ContentType.objects.get_for_model(Image)
        content = get_object_or_404(
            Content,
            content_type=image_type,
            object_id=image_id,
            module__course__students=request.user,
        )
        image_obj = content.item

        if not image_obj or not image_obj.file:
            raise Http404("Image not found.")

        filename = os.path.basename(image_obj.file.name)

        try:
            return FileResponse(
                image_obj.file.open("rb"),
                filename=filename,
            )
        except FileNotFoundError as exc:
            raise Http404("Image not found.") from exc

# pdf previw page

@method_decorator(xframe_options_exempt, name="dispatch")
class ModuleFilePreviewView(LoginRequiredMixin, View):
    """
    Serve module file inline (for PDF browser preview) to enrolled users.
    """
    def get(self, request, file_id):
        file_type = ContentType.objects.get_for_model(File)
        content = get_object_or_404(
            Content,
            content_type=file_type,
            object_id=file_id,
            module__course__students=request.user,
        )
        file_obj = content.item

        if not file_obj or not file_obj.file:
            raise Http404("File not found.")

        filename = os.path.basename(file_obj.file.name)
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/octet-stream"

        try:
            response = FileResponse(
                file_obj.file.open("rb"),
                as_attachment=False,
                filename=filename,
                content_type=content_type,
            )
        except FileNotFoundError as exc:
            raise Http404("File not found.") from exc

        # Force inline rendering in browser viewers (PDF/image support).
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        patch_response_headers(response, cache_timeout=0)
        return response


# Online count
class PresencePingView(LoginRequiredMixin, View):
    def post(self, request):
        online_count = touch_user_presence(request.user.id)
        return JsonResponse({"online_count": online_count})


class StopLocalStackView(LoginRequiredMixin, View):
    """
    Stop local development services (Django + Redis) by launching stop.ps1.
    This is intentionally restricted to privileged users on localhost only.
    """

    def post(self, request):
        # Guard 1: only staff/superusers can trigger a local shutdown.
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({"error": "Forbidden"}, status=403)

        # Guard 2: only allow requests coming from local loopback addresses.
        remote_addr = request.META.get("REMOTE_ADDR")
        if remote_addr not in {"127.0.0.1", "::1"}:
            return JsonResponse({"error": "Localhost only"}, status=403)

        # Guard 3: only allow localhost host headers for extra safety.
        host = request.get_host().split(":", 1)[0]
        if host not in {"127.0.0.1", "localhost"}:
            return JsonResponse({"error": "Localhost host only"}, status=403)

        # Resolve the local stop script from project root.
        stop_script = Path(settings.BASE_DIR) / "stop.ps1"
        if not stop_script.exists():
            return JsonResponse({"error": "stop.ps1 not found"}, status=500)

        # Delay execution slightly so this request can return before the server stops itself.
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"Start-Sleep -Milliseconds 650; & '{stop_script}'",
        ]

        # Detach process on Windows so it survives independently of this request thread.
        creationflags = 0
        if os.name == "nt":
            creationflags = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )

        # Launch stop script without inheriting stdio handles.
        subprocess.Popen(
            command,
            cwd=str(settings.BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )

        # Return immediate confirmation; shutdown continues asynchronously.
        return JsonResponse({"status": "stopping"})
