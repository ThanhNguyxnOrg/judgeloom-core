from __future__ import annotations

from django.db import models

from core.models import TimestampedModel


class TicketMessage(TimestampedModel):
    """A message posted inside a support ticket."""

    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    author = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    body = models.TextField()

    def __str__(self) -> str:
        """Return human-readable message label."""

        return f"Message #{self.pk} on Ticket #{self.ticket_id}"

    class Meta:
        db_table = "tickets_ticket_message"
        verbose_name = "Ticket message"
        verbose_name_plural = "Ticket messages"
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="ticket_msg_ticket_created_idx"),
            models.Index(fields=["author"], name="tickets_message_author_idx"),
        ]
