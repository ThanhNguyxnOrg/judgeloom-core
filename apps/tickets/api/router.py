from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.tickets.api.schemas import (
    TicketCreateIn,
    TicketDetailOut,
    TicketListOut,
    TicketMessageIn,
    TicketMessageOut,
    TicketUpdateIn,
)
from apps.tickets.models import Ticket
from apps.tickets.services import TicketService
from core.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from django.http import HttpRequest

router = Router(tags=["tickets"])


def _require_authenticated(user: Any) -> None:
    """Ensure current user is authenticated.

    Args:
        user: Request user.

    Raises:
        PermissionDeniedError: If user is anonymous.
    """

    if not getattr(user, "is_authenticated", False):
        raise PermissionDeniedError("Authentication required.")


def _require_staff(user: Any) -> None:
    """Ensure current user is a staff member.

    Args:
        user: Request user.

    Raises:
        PermissionDeniedError: If user is not staff.
    """

    _require_authenticated(user)
    if not getattr(user, "is_staff", False):
        raise PermissionDeniedError("Staff access required.")


def _can_access_ticket(user: Any, ticket: Ticket) -> bool:
    """Check if the user can access a ticket."""

    if getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
        return True
    if ticket.is_public:
        return True
    return bool(getattr(user, "is_authenticated", False) and ticket.author_id == user.id)


def _to_ticket_list_out(ticket: Ticket) -> TicketListOut:
    """Serialize ticket list response."""

    return TicketListOut(
        id=ticket.id,
        title=ticket.title,
        author_id=ticket.author_id,
        status=ticket.status,
        priority=ticket.priority,
        is_public=ticket.is_public,
        created_at=ticket.created_at,
    )


def _to_ticket_detail_out(ticket: Ticket) -> TicketDetailOut:
    """Serialize detailed ticket response."""

    messages = [
        TicketMessageOut(
            id=message.id,
            ticket_id=message.ticket_id,
            author_id=message.author_id,
            body=message.body,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )
        for message in ticket.messages.select_related("author").all().order_by("created_at")
    ]
    return TicketDetailOut(
        id=ticket.id,
        title=ticket.title,
        author_id=ticket.author_id,
        status=ticket.status,
        priority=ticket.priority,
        is_public=ticket.is_public,
        created_at=ticket.created_at,
        body=ticket.body,
        linked_problem_id=ticket.linked_problem_id,
        linked_contest_id=ticket.linked_contest_id,
        assignee_ids=list(ticket.assignees.values_list("id", flat=True)),
        messages=messages,
    )


@router.get("/", response=list[TicketListOut])
def list_tickets(request: HttpRequest, status: str | None = None, user_id: int | None = None) -> list[TicketListOut]:
    """List tickets with optional status and user filters."""

    queryset = TicketService.get_user_tickets(request.user)
    if status:
        queryset = queryset.filter(status=status)

    if user_id is not None and (getattr(request.user, "is_staff", False) or request.user.id == user_id):
        queryset = queryset.filter(author_id=user_id)

    tickets = queryset.order_by("-created_at").distinct()
    return [_to_ticket_list_out(ticket) for ticket in tickets]


@router.post("/", response=TicketDetailOut)
def create_ticket(request: HttpRequest, payload: TicketCreateIn) -> TicketDetailOut:
    """Create a new support ticket."""

    _require_authenticated(request.user)
    ticket = TicketService.create_ticket(
        title=payload.title,
        author=request.user,
        body=payload.body,
        priority=payload.priority,
        is_public=payload.is_public,
        linked_problem_id=payload.linked_problem_id,
        linked_contest_id=payload.linked_contest_id,
    )
    return _to_ticket_detail_out(ticket)


@router.get("/{ticket_id}", response=TicketDetailOut)
def get_ticket_detail(request: HttpRequest, ticket_id: int) -> TicketDetailOut:
    """Return full ticket detail including messages."""

    ticket = get_object_or_404(Ticket.objects.select_related("author"), id=ticket_id)
    if not _can_access_ticket(request.user, ticket):
        raise PermissionDeniedError("You do not have permission to view this ticket.")
    return _to_ticket_detail_out(ticket)


@router.patch("/{ticket_id}", response=TicketDetailOut)
def update_ticket(request: HttpRequest, ticket_id: int, payload: TicketUpdateIn) -> TicketDetailOut:
    """Update a support ticket."""

    _require_authenticated(request.user)
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.author_id != request.user.id and not getattr(request.user, "is_staff", False):
        raise PermissionDeniedError("You do not have permission to update this ticket.")

    data = payload.model_dump(exclude_none=True)
    ticket = TicketService.update_ticket(ticket, **data)
    return _to_ticket_detail_out(ticket)


@router.post("/{ticket_id}/messages", response=TicketMessageOut)
def add_message(request: HttpRequest, ticket_id: int, payload: TicketMessageIn) -> TicketMessageOut:
    """Add a message to an existing ticket."""

    _require_authenticated(request.user)
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if not _can_access_ticket(request.user, ticket):
        raise PermissionDeniedError("You do not have permission to interact with this ticket.")

    message = TicketService.add_message(ticket=ticket, author=request.user, body=payload.body)
    return TicketMessageOut(
        id=message.id,
        ticket_id=message.ticket_id,
        author_id=message.author_id,
        body=message.body,
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


@router.post("/{ticket_id}/close", response=TicketDetailOut)
def close_ticket(request: HttpRequest, ticket_id: int) -> TicketDetailOut:
    """Close a support ticket."""

    _require_authenticated(request.user)
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.author_id != request.user.id and not getattr(request.user, "is_staff", False):
        raise PermissionDeniedError("You do not have permission to close this ticket.")

    ticket = TicketService.close_ticket(ticket)
    return _to_ticket_detail_out(ticket)


@router.post("/{ticket_id}/reopen", response=TicketDetailOut)
def reopen_ticket(request: HttpRequest, ticket_id: int) -> TicketDetailOut:
    """Reopen a closed or resolved support ticket."""

    _require_authenticated(request.user)
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.author_id != request.user.id and not getattr(request.user, "is_staff", False):
        raise PermissionDeniedError("You do not have permission to reopen this ticket.")

    ticket = TicketService.reopen_ticket(ticket)
    return _to_ticket_detail_out(ticket)


@router.post("/{ticket_id}/assign", response=TicketDetailOut)
def assign_ticket(request: HttpRequest, ticket_id: int, assignee_id: int) -> TicketDetailOut:
    """Assign a ticket to another user. Staff only."""

    _require_staff(request.user)
    ticket = get_object_or_404(Ticket, id=ticket_id)
    assignee = get_object_or_404(type(request.user), id=assignee_id)
    ticket = TicketService.assign_ticket(ticket, assignee)
    return _to_ticket_detail_out(ticket)
