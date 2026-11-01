"""
JudgeLoom — Ticket Tests
============================

Unit tests for the Ticket model and status logic.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.contests.constants import ContestVisibility
from apps.problems.constants import ProblemVisibility
from apps.tickets.constants import TicketStatus
from tests.factories import ContestFactory, ProblemFactory, TicketFactory


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


@pytest.mark.django_db
class TestTicketLinkVisibility:
    def test_cannot_link_private_problem_or_contest(self, user):
        private_problem = ProblemFactory(visibility=ProblemVisibility.PRIVATE)
        private_contest = ContestFactory(visibility=ContestVisibility.PRIVATE)
        client = Client()
        client.force_login(user)

        problem_response = client.post(
            "/api/tickets/",
            data=f'{{"title":"Help","body":"body","linked_problem_id":{private_problem.id}}}',
            content_type="application/json",
        )
        assert problem_response.status_code == 403

        contest_response = client.post(
            "/api/tickets/",
            data=f'{{"title":"Help","body":"body","linked_contest_id":{private_contest.id}}}',
            content_type="application/json",
        )
        assert contest_response.status_code == 403

    def test_can_link_public_problem(self, user):
        problem = ProblemFactory(visibility=ProblemVisibility.PUBLIC)
        client = Client()
        client.force_login(user)

        response = client.post(
            "/api/tickets/",
            data=f'{{"title":"Help","body":"body","linked_problem_id":{problem.id}}}',
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["linked_problem_id"] == problem.id

    def test_staff_can_link_private_problem_and_author_cannot_update_to_private(self, user, admin_user):
        private_problem = ProblemFactory(visibility=ProblemVisibility.PRIVATE)
        staff = Client()
        staff.force_login(admin_user)
        response = staff.post(
            "/api/tickets/",
            data=f'{{"title":"Help","body":"body","linked_problem_id":{private_problem.id}}}',
            content_type="application/json",
        )
        assert response.status_code == 200

        ticket = TicketFactory(author=user)
        author = Client()
        author.force_login(user)
        response = author.patch(
            f"/api/tickets/{ticket.id}",
            data=f'{{"linked_problem_id":{private_problem.id}}}',
            content_type="application/json",
        )
        assert response.status_code == 403
