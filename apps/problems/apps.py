from __future__ import annotations

from django.apps import AppConfig

class ProblemsConfig(AppConfig):
    """Application configuration for the problems app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.problems"
    label = "problems"
    verbose_name = "Problems"
