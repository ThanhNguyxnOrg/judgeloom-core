from __future__ import annotations

from django.apps import AppConfig


class ContestsConfig(AppConfig):
    """Application configuration for contests domain."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.contests"
    verbose_name = "Contests"

    def ready(self) -> None:
        """Import signal handlers when the app registry is ready."""
        import apps.contests.signals  # noqa: F401
