from __future__ import annotations

from django.contrib import admin

from apps.problems.models import (
    LanguageLimit,
    License,
    Problem,
    ProblemPackage,
    ProblemTestCase,
    Solution,
)


class ProblemTestCaseInline(admin.TabularInline):
    """Read-only inline for test cases belonging to one package."""

    model = ProblemTestCase
    extra = 0
    can_delete = False
    readonly_fields = (
        "order",
        "input_file",
        "output_file",
        "input_sha256",
        "output_sha256",
        "points",
        "group",
        "is_pretest",
        "batch_number",
    )


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    """Admin configuration for problem records."""

    list_display = ("code", "name", "visibility", "difficulty", "points", "is_manually_managed")
    list_filter = ("visibility", "difficulty", "partial_score", "short_circuit")
    search_fields = ("code", "name", "summary")
    filter_horizontal = ("authors", "curators", "testers", "languages_allowed", "organizations")


@admin.register(ProblemPackage)
class ProblemPackageAdmin(admin.ModelAdmin):
    """Admin configuration for immutable problem packages."""

    list_display = ("problem", "version", "sha256", "is_active", "size_bytes", "created_at")
    list_filter = ("is_active",)
    search_fields = ("problem__code", "problem__name", "sha256")
    readonly_fields = ("problem", "version", "sha256", "manifest", "archive", "size_bytes", "created_at", "updated_at")
    inlines = (ProblemTestCaseInline,)
    actions = ("activate_packages",)

    def has_add_permission(self, request):  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False

    @admin.action(description="Activate selected package")
    def activate_packages(self, request, queryset):  # type: ignore[no-untyped-def]
        for package in queryset:
            ProblemPackage.objects.filter(problem=package.problem).exclude(pk=package.pk).update(is_active=False)
            if not package.is_active:
                package.is_active = True
                package.save(update_fields=["is_active", "updated_at"])


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    """Admin configuration for problem solutions."""

    list_display = ("problem", "author", "is_public", "verdict", "created_at")
    list_filter = ("is_public", "verdict")
    search_fields = ("problem__code", "author__username")


admin.site.register(LanguageLimit)
admin.site.register(License)
