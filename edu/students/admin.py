from django.contrib import admin
from .models import ContentProgress, CourseProgress, ModuleProgress


@admin.register(CourseProgress)
class CourseProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "progress_percent", "completed", "completed_at", "last_accessed")
    list_filter = ("completed", "course")
    search_fields = ("user__username", "course__title")


@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "module", "progress_percent", "completed", "time_spent", "last_accessed")
    list_filter = ("completed", "course")
    search_fields = ("user__username", "module__title", "course__title")


@admin.register(ContentProgress)
class ContentProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "module", "content", "content_type", "progress_percent", "completed", "updated")
    list_filter = ("content_type", "completed", "course")
    search_fields = ("user__username", "course__title", "module__title", "content__id")
