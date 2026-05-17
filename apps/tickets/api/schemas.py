from __future__ import annotations

from typing import TYPE_CHECKING

from ninja import Schema

if TYPE_CHECKING:
    from datetime import datetime


class TicketCreateIn(Schema):
    """Payload for creating a support ticket."""

    title: str
    body: str
    linked_problem_id: int | None = None
    linked_contest_id: int | None = None
    priority: str = "medium"
    is_public: bool = True


class TicketUpdateIn(Schema):
    """Payload for updating a support ticket."""

    title: str | None = None
    body: str | None = None
    status: str | None = None
    priority: str | None = None
    linked_problem_id: int | None = None
    linked_contest_id: int | None = None
    is_public: bool | None = None


class TicketListOut(Schema):
    """Ticket list item response."""

    id: int
    title: str
    author_id: int
    status: str
    priority: str
    is_public: bool
    created_at: datetime


class TicketMessageIn(Schema):
    """Payload for adding a message to a ticket."""

    body: str


class TicketMessageOut(Schema):
    """Ticket message response."""

    id: int
    ticket_id: int
    author_id: int
    body: str
    created_at: datetime
    updated_at: datetime


class TicketDetailOut(TicketListOut):
    """Detailed ticket response with messages."""

    body: str
    linked_problem_id: int | None = None
    linked_contest_id: int | None = None
    assignee_ids: list[int]
    messages: list[TicketMessageOut]
