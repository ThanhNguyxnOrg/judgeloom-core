from __future__ import annotations

from django.contrib import admin

from apps.content.models import BlogPost, Comment, NavigationItem

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    """Admin configuration for blog posts."""

    list_display = ("title", "author", "visibility", "is_pinned", "publish_date")
    list_filter = ("visibility", "is_pinned")
    search_fields = ("title", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("organizations",)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Admin configuration for comments."""

    list_display = ("id", "post", "author", "visibility", "score", "path")
    list_filter = ("visibility",)
    search_fields = ("body", "path")
    raw_id_fields = ("post", "author", "parent")

@admin.register(NavigationItem)
class NavigationItemAdmin(admin.ModelAdmin):
    """Admin configuration for navigation items."""

    list_display = ("key", "label", "url", "parent", "order", "is_external")
    list_filter = ("is_external",)
    search_fields = ("key", "label", "url")
    raw_id_fields = ("parent",)
