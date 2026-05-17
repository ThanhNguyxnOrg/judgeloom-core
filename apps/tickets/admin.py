from __future__ import annotations

from django.contrib import admin

from apps.tickets.models import Ticket, TicketMessage


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """Admin configuration for support tickets."""

    list_display = ("id", "title", "author", "status", "priority", "is_public", "created_at")
    list_filter = ("status", "priority", "is_public")
    search_fields = ("title", "body")
    raw_id_fields = ("author", "linked_problem", "linked_contest")
    filter_horizontal = ("assignees",)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    """Admin configuration for ticket messages."""

    list_display = ("id", "ticket", "author", "created_at")
    search_fields = ("body",)
    raw_id_fields = ("ticket", "author")
