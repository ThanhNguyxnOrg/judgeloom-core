"""
JudgeLoom — Contest Tests
============================

Unit tests for Contest and ContestParticipation models.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.contests.constants import ContestFormat, ParticipationStatus
from tests.factories import ContestFactory, ContestParticipationFactory, UserFactory


@pytest.mark.django_db
class TestContestModel:
    """Tests for the Contest model."""

    def test_create_contest(self, contest):
        """Factory creates a valid active contest."""
        assert contest.pk is not None
        assert contest.format_name == ContestFormat.DEFAULT

    def test_contest_str(self, contest):
        """__str__ includes key and name."""
        result = str(contest)
        assert contest.key in result
        assert contest.name in result

    def test_is_active(self, contest):
        """Contest within time range is active."""
        assert contest.is_active is True

    def test_is_finished(self, finished_contest):
        """Contest past end_time is finished."""
        assert finished_contest.is_finished is True

    def test_is_upcoming(self):
        """Contest before start_time is upcoming."""
        future = ContestFactory(
            key="future1",
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=4),
        )
        assert future.is_upcoming is True

    def test_duration(self, contest):
        """Duration is end_time - start_time."""
        assert contest.duration == contest.end_time - contest.start_time

    def test_time_remaining_active(self, contest):
        """Active contest has positive remaining time."""
        assert contest.time_remaining > timedelta(0)

    def test_time_remaining_finished(self, finished_contest):
        """Finished contest has zero remaining time."""
        assert finished_contest.time_remaining == timedelta(0)


@pytest.mark.django_db
class TestContestParticipation:
    """Tests for the ContestParticipation model."""

    def test_create_participation(self, participation):
        """Factory creates a valid live participation."""
        assert participation.pk is not None
        assert participation.status == ParticipationStatus.LIVE

    def test_live_property(self, participation):
        """Live participation returns True for .live."""
        assert participation.live is True

    def test_participation_str(self, participation):
        """__str__ includes user and contest info."""
        result = str(participation)
        assert "@" in result
