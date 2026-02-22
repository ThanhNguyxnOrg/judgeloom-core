"""
JudgeLoom — Account Tests
============================

Unit tests for the User model, user creation, and rating logic.
"""

from __future__ import annotations

import pytest

from apps.accounts.constants import UserRole
from apps.accounts.models import User
from tests.factories import AdminUserFactory, UserFactory


@pytest.mark.django_db
class TestUserModel:
    """Tests for the User model."""

    def test_create_user(self, user):
        """User factory creates a valid participant."""
        assert user.pk is not None
        assert user.role == UserRole.PARTICIPANT
        assert user.is_active is True

    def test_user_str(self, user):
        """__str__ returns the username."""
        assert str(user) == user.username

    def test_display_name_with_full_name(self, user):
        """display_name returns full name when set."""
        user.first_name = "Alice"
        user.last_name = "Smith"
        user.save()
        assert user.display_name == "Alice Smith"

    def test_display_name_fallback(self, user):
        """display_name falls back to username."""
        assert user.display_name == user.username

    def test_admin_user_factory(self, admin_user):
        """Admin factory creates a superuser with admin role."""
        assert admin_user.is_superuser is True
        assert admin_user.is_staff is True
        assert admin_user.role == UserRole.ADMIN

    def test_rating_class_newbie(self, user):
        """Default rating yields newbie CSS class."""
        assert user.rating == 0
        assert user.get_rating_class() == "user-newbie"

    def test_rating_class_expert(self, user):
        """Rating of 1600 yields expert CSS class."""
        user.rating = 1600
        assert user.get_rating_class() == "user-expert"

    def test_is_contest_participant_false(self, user):
        """is_contest_participant is False with no active contest."""
        assert user.is_contest_participant is False

    def test_calculate_contribution(self, user):
        """Contribution score is a non-negative float."""
        score = user.calculate_contribution()
        assert isinstance(score, float)
        assert score >= 0.0
