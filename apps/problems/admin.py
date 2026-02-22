from __future__ import annotations

from django.contrib import admin

from apps.problems.models import LanguageLimit, License, Problem, ProblemTestCase, ProblemTestData, Solution

class ProblemTestCaseInline(admin.TabularInline):
    """Inline admin for managing test cases under test data."""

    model = ProblemTestCase
    extra = 0

@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    """Admin configuration for problem records."""

    list_display = ("code", "name", "visibility", "difficulty", "points", "is_manually_managed")
    list_filter = ("visibility", "difficulty", "partial_score", "short_circuit")
    search_fields = ("code", "name", "summary")
    filter_horizontal = ("authors", "curators", "testers", "languages_allowed", "organizations")

@admin.register(ProblemTestData)
class ProblemTestDataAdmin(admin.ModelAdmin):
    """Admin configuration for problem test data."""

    list_display = ("problem", "checker", "output_prefix", "output_limit", "updated_at")
    list_filter = ("checker",)
    search_fields = ("problem__code", "problem__name")
    inlines = (ProblemTestCaseInline,)

@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    """Admin configuration for problem solutions."""

    list_display = ("problem", "author", "is_public", "verdict", "created_at")
    list_filter = ("is_public", "verdict")
    search_fields = ("problem__code", "author__username")

admin.site.register(LanguageLimit)
admin.site.register(License)
