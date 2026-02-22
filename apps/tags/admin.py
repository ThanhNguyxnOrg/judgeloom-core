from __future__ import annotations

from django.contrib import admin

from apps.tags.models import Tag, TagGroup

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin configuration for tag entities."""

    list_display = ("name", "code")
    search_fields = ("name", "code")

@admin.register(TagGroup)
class TagGroupAdmin(admin.ModelAdmin):
    """Admin configuration for tag groups."""

    list_display = ("name", "order")
    search_fields = ("name",)
    filter_horizontal = ("tags",)
