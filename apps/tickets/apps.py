from __future__ import annotations

from django.apps import AppConfig

class TicketsConfig(AppConfig):
    """Application configuration for the tickets app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tickets"
    label = "tickets"
    verbose_name = "Tickets"
