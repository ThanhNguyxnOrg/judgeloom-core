"""
JudgeLoom — Rating Tests
============================

Unit tests for the Rating model and rating sync signals.
"""

from __future__ import annotations

import pytest

from tests.factories import (
    ContestFactory,
    ContestParticipationFactory,
    RatingFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestRatingModel:
    """Tests for the Rating model."""

    def test_create_rating(self):
        """Factory creates a valid rating record."""
        user = UserFactory(username="rated_user")
        contest = ContestFactory(key="rated_contest", is_rated=True)
        participation = ContestParticipationFactory(user=user, contest=contest)
        rating = RatingFactory(
            user=user,
            contest=contest,
            participation=participation,
        )
        assert rating.pk is not None
        assert rating.rating_after > 0

    def test_rating_str(self):
        """__str__ shows delta with sign."""
        user = UserFactory(username="str_user")
        contest = ContestFactory(key="str_contest")
        participation = ContestParticipationFactory(user=user, contest=contest)
        rating = RatingFactory(
            user=user,
            contest=contest,
            participation=participation,
            rating_before=1500,
            rating_after=1550,
        )
        result = str(rating)
        assert "+50" in result

    def test_negative_delta_str(self):
        """__str__ shows negative delta."""
        user = UserFactory(username="neg_user")
        contest = ContestFactory(key="neg_contest")
        participation = ContestParticipationFactory(user=user, contest=contest)
        rating = RatingFactory(
            user=user,
            contest=contest,
            participation=participation,
            rating_before=1600,
            rating_after=1550,
        )
        result = str(rating)
        assert "-50" in result


@pytest.mark.django_db
class TestRatingSignals:
    """Tests for rating sync signals."""

    def test_rating_syncs_to_user(self):
        """Creating a rating updates user.rating via signal."""
        user = UserFactory(username="sync_user", rating=1500)
        contest = ContestFactory(key="sync_contest")
        participation = ContestParticipationFactory(user=user, contest=contest)
        RatingFactory(
            user=user,
            contest=contest,
            participation=participation,
            rating_before=1500,
            rating_after=1600,
        )
        user.refresh_from_db()
        assert user.rating == 1600
