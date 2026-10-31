from __future__ import annotations

from django.contrib import admin

from apps.judge.models import Judge, JudgeJob, Language, RuntimeVersion


@admin.register(Judge)
class JudgeAdmin(admin.ModelAdmin):
    """Admin configuration for judge worker records."""

    list_display = ("name", "online", "is_blocked", "protocol_version", "current_load", "last_seen", "updated_at")
    list_filter = ("online", "is_blocked", "protocol_version", "created_at")
    search_fields = ("name", "hostname", "description")
    filter_horizontal = ("problems", "runtimes")
    readonly_fields = (
        "created_at",
        "updated_at",
        "start_time",
        "last_seen",
        "protocol_version",
        "capabilities",
        "current_load",
        "token_prefix",
    )


@admin.register(JudgeJob)
class JudgeJobAdmin(admin.ModelAdmin):
    """Read-mostly admin for judge jobs."""

    list_display = ("submission", "status", "priority", "claimed_by", "attempts", "lease_expires_at", "created_at")
    list_filter = ("status", "priority", "created_at")
    search_fields = ("submission__id", "submission__problem__code", "claimed_by__name")
    autocomplete_fields = ("submission", "package", "language", "claimed_by")
    readonly_fields = ("created_at", "updated_at", "claimed_at", "started_at", "finished_at")


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    """Admin configuration for language records."""

    list_display = ("key", "name", "short_name", "extension", "is_enabled")
    list_filter = ("is_enabled", "created_at")
    search_fields = ("key", "name", "short_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RuntimeVersion)
class RuntimeVersionAdmin(admin.ModelAdmin):
    """Admin configuration for runtime version records."""

    list_display = ("judge", "language", "name", "version", "priority")
    list_filter = ("language", "judge")
    search_fields = ("name", "version", "judge__name", "language__key")
    autocomplete_fields = ("judge", "language")
    readonly_fields = ("created_at", "updated_at")
