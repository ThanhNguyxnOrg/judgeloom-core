from __future__ import annotations

from django.apps import AppConfig

class TagsConfig(AppConfig):
    """Application configuration for the tags app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tags"
    label = "tags"
    verbose_name = "Tags"
