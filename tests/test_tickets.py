"""
JudgeLoom — Ticket Tests
============================

Unit tests for the Ticket model and status logic.
"""

from __future__ import annotations

import pytest

from apps.tickets.constants import TicketPriority, TicketStatus
from tests.factories import TicketFactory


@pytest.mark.django_db
class TestTicketModel:
    """Tests for the Ticket model."""

    def test_create_ticket(self, ticket):
        """Factory creates a valid open ticket."""
        assert ticket.pk is not None
        assert ticket.status == TicketStatus.OPEN

    def test_ticket_str(self, ticket):
        """__str__ includes ticket number and title."""
        result = str(ticket)
        assert "Ticket #" in result
        assert ticket.title in result

    def test_is_open_when_open(self, ticket):
        """Open ticket reports is_open correctly."""
        assert ticket.is_open is True

    def test_is_open_when_in_progress(self, ticket):
        """In-progress ticket is still open."""
        ticket.status = TicketStatus.IN_PROGRESS
        assert ticket.is_open is True

    def test_is_not_open_when_resolved(self, ticket):
        """Resolved ticket is not open."""
        ticket.status = TicketStatus.RESOLVED
        assert ticket.is_open is False

    def test_is_resolved_when_closed(self, ticket):
        """Closed ticket reports is_resolved correctly."""
        ticket.status = TicketStatus.CLOSED
        assert ticket.is_resolved is True

    def test_is_resolved_false_when_open(self, ticket):
        """Open ticket is not resolved."""
        assert ticket.is_resolved is False
