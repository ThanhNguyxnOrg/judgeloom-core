from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.tickets.constants import TicketStatus
from apps.tickets.models import Ticket, TicketMessage

if TYPE_CHECKING:
    from django.db.models import QuerySet


class TicketService:
    """Business operations for support tickets."""

    @staticmethod
    def create_ticket(title: str, author: Any, body: str, **kwargs: Any) -> Ticket:
        """Create and persist a new ticket.

        Args:
            title: Ticket title.
            author: Ticket author.
            body: Ticket message body.
            **kwargs: Optional ticket fields.

        Returns:
            Created ticket instance.
        """

        allowed_fields = {
            "linked_problem",
            "linked_problem_id",
            "linked_contest",
            "linked_contest_id",
            "status",
            "priority",
            "is_public",
        }
        extra_fields = {key: value for key, value in kwargs.items() if key in allowed_fields}
        return Ticket.objects.create(title=title, author=author, body=body, **extra_fields)

    @staticmethod
    def update_ticket(ticket: Ticket, **kwargs: Any) -> Ticket:
        """Update mutable ticket fields.

        Args:
            ticket: Existing ticket instance.
            **kwargs: Updated values.

        Returns:
            Updated ticket instance.
        """

        mutable_fields = {
            "title",
            "body",
            "status",
            "priority",
            "linked_problem",
            "linked_contest",
            "is_public",
        }
        updated_fields: list[str] = []
        for key, value in kwargs.items():
            if key in mutable_fields:
                setattr(ticket, key, value)
                updated_fields.append(key)

        if updated_fields:
            ticket.save(update_fields=updated_fields)
        return ticket

    @staticmethod
    def close_ticket(ticket: Ticket) -> Ticket:
        """Move a ticket to closed state.

        Args:
            ticket: Ticket to close.

        Returns:
            Updated ticket.
        """

        ticket.status = TicketStatus.CLOSED
        ticket.save(update_fields=["status"])
        return ticket

    @staticmethod
    def reopen_ticket(ticket: Ticket) -> Ticket:
        """Reopen a closed or resolved ticket.

        Args:
            ticket: Ticket to reopen.

        Returns:
            Updated ticket.
        """

        ticket.status = TicketStatus.OPEN
        ticket.save(update_fields=["status"])
        return ticket

    @staticmethod
    def assign_ticket(ticket: Ticket, assignee: Any) -> Ticket:
        """Assign a ticket to a user.

        Args:
            ticket: Target ticket.
            assignee: User to assign.

        Returns:
            Updated ticket instance.
        """

        ticket.assignees.add(assignee)
        return ticket

    @staticmethod
    def add_message(ticket: Ticket, author: Any, body: str) -> TicketMessage:
        """Add a new message to a ticket.

        Args:
            ticket: Ticket receiving the message.
            author: Message author.
            body: Message body text.

        Returns:
            Created ticket message.
        """

        return TicketMessage.objects.create(ticket=ticket, author=author, body=body)

    @staticmethod
    def get_user_tickets(user: Any) -> QuerySet[Ticket]:
        """Return all tickets visible to a user.

        Args:
            user: Request user.

        Returns:
            Filtered queryset of tickets.
        """

        base_queryset = Ticket.objects.select_related("author", "linked_problem", "linked_contest").prefetch_related(
            "assignees"
        )

        if getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
            return base_queryset

        if getattr(user, "is_authenticated", False):
            return base_queryset.filter(is_public=True) | base_queryset.filter(author=user)

        return base_queryset.filter(is_public=True)

    @staticmethod
    def get_open_tickets() -> QuerySet[Ticket]:
        """Return tickets currently in open workflow states.

        Returns:
            QuerySet containing open and in-progress tickets.
        """

        return Ticket.objects.select_related("author").filter(status__in=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
