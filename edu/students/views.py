"""
Student-facing views:
- account registration
- course enrollment
- enrolled course list/detail
"""


# URL builder used for redirects after successful actions.
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy

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
from courses.models import Course, Module
from .services import add_time_spent, mark_module_completed
from .services import get_overall_progress, get_course_time_spent


import redis


r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
)



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

class StudentCourseDetailView(LoginRequiredMixin, DetailView):
    model = Course
    template_name = "students/course/detail.html"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(students__in=[self.request.user])
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        modules = course.modules.all()
        user = self.request.user

        if "module_id" in self.kwargs:
            module = get_object_or_404(Module, id=self.kwargs["module_id"], course=course)
        else:
            module = modules.first()

        context["module"] = module

        # --- FIX: mark module as completed when opened ---
        if module:
            mark_module_completed(user, module)

        context['course_time'] = get_course_time_spent(user, course)

        return context


class MarkModuleCompleteView(View):
    def post(self, request, module_id):
        module = get_object_or_404(Module, id=module_id)

        mark_module_completed(request.user, module)

        return JsonResponse({'status': 'completed'})

class TrackTimeView(View):
    def post(self, request, module_id):
        module = get_object_or_404(Module, id=module_id)
        
        try:
            # Handle both standard POST and JSON/Beacon payloads
            seconds = int(request.POST.get('seconds', 0))
            
            if seconds > 0:
                add_time_spent(request.user, module, seconds)
                return JsonResponse({'status': 'tracked', 'seconds': seconds})
            
            return JsonResponse({'status': 'ignored', 'reason': '0 seconds'})
            
        except ValueError:
            return JsonResponse({'status': 'error', 'reason': 'Invalid seconds value'}, status=400)


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'students/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['overall_progress'] = get_overall_progress(user)
        context['courses'] = user.courses_joined.all()

        return context