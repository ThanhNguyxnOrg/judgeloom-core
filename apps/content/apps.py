from __future__ import annotations

from django.apps import AppConfig

class ContentConfig(AppConfig):
    """Application configuration for the content app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"
    label = "content"
    verbose_name = "Content"
