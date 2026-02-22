from __future__ import annotations

from django.apps import AppConfig


class SubmissionsConfig(AppConfig):
    """Application configuration for submission lifecycle management."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.submissions"
    label = "submissions"
    verbose_name = "Submissions"

    def ready(self) -> None:
        """Import signal handlers when the app registry is ready."""
        import apps.submissions.signals  # noqa: F401
