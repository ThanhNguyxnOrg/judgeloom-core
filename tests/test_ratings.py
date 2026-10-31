"""
JudgeLoom — Rating Tests
============================

Unit tests for the Rating model and rating sync signals.
"""

from __future__ import annotations

import pytest

from django.test import Client

from apps.contests.constants import ContestVisibility, ParticipationStatus
from apps.ratings.models import Rating
from apps.ratings.services.rating_service import RatingService
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
class TestRatingApiVisibility:
    def test_private_contest_rating_changes_require_access(self):
        private = ContestFactory(key="private-ratings", visibility=ContestVisibility.PRIVATE)
        client = Client()

        assert client.get(f"/api/ratings/contest/{private.key}").status_code == 403

        public = ContestFactory(key="public-ratings", visibility=ContestVisibility.PUBLIC)
        assert client.get(f"/api/ratings/contest/{public.key}").status_code == 200


@pytest.mark.django_db
class TestRatingCalculation:
    def test_unrated_contest_produces_no_ratings(self):
        contest = ContestFactory(is_rated=False)
        user = UserFactory()
        ContestParticipationFactory(user=user, contest=contest)

        assert RatingService.calculate_ratings(contest) == []
        assert Rating.objects.filter(contest=contest).count() == 0

    def test_only_live_non_disqualified_participants_are_rated(self):
        contest = ContestFactory(is_rated=True, rate_all=True)
        live = UserFactory()
        virtual = UserFactory()
        disqualified = UserFactory()
        ContestParticipationFactory(user=live, contest=contest)
        ContestParticipationFactory(
            user=virtual,
            contest=contest,
            status=ParticipationStatus.VIRTUAL,
            virtual_start=contest.start_time,
        )
        ContestParticipationFactory(user=disqualified, contest=contest, is_disqualified=True)

        rows = RatingService.calculate_ratings(contest)

        assert {row.user_id for row in rows} == {live.id}
        virtual.refresh_from_db()
        disqualified.refresh_from_db()
        assert virtual.rating == 0
        assert disqualified.rating == 0

    def test_rate_excluded_user_is_not_rated(self):
        contest = ContestFactory(is_rated=True, rate_all=True)
        user = UserFactory()
        ContestParticipationFactory(user=user, contest=contest)
        contest.rate_exclude.add(user)

        rows = RatingService.calculate_ratings(contest)

        assert rows == []
        assert Rating.objects.filter(contest=contest).count() == 0

    def test_calculation_is_idempotent_without_force(self):
        contest = ContestFactory(is_rated=True, rate_all=True)
        user = UserFactory()
        ContestParticipationFactory(user=user, contest=contest)

        first = RatingService.calculate_ratings(contest)
        user.refresh_from_db()
        rating_after_first = user.rating
        second = RatingService.calculate_ratings(contest)
        user.refresh_from_db()

        assert [row.pk for row in first] == [row.pk for row in second]
        assert Rating.objects.filter(contest=contest).count() == 1
        assert user.rating == rating_after_first

    def test_force_recalculation_does_not_double_apply(self):
        contest = ContestFactory(is_rated=True, rate_all=True)
        user = UserFactory()
        ContestParticipationFactory(user=user, contest=contest)

        RatingService.calculate_ratings(contest)
        user.refresh_from_db()
        rating_after_first = user.rating
        RatingService.calculate_ratings(contest, force=True)
        user.refresh_from_db()

        assert user.rating == rating_after_first
        assert Rating.objects.filter(contest=contest).count() == 1


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
