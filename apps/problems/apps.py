from __future__ import annotations

from django.apps import AppConfig


class ProblemsConfig(AppConfig):
    """Application configuration for the problems app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.problems"
    label = "problems"
    verbose_name = "Problems"

    def ready(self) -> None:
        """Import signal handlers when the app registry is ready."""
        import apps.problems.signals  # noqa: F401
