"""
JudgeLoom — Problem Tests
============================

Unit tests for Problem model properties and accessibility logic.
"""

from __future__ import annotations

import pytest

from apps.problems.constants import ProblemVisibility
from tests.factories import ProblemFactory, UserFactory


@pytest.mark.django_db
class TestProblemModel:
    """Tests for the Problem model."""

    def test_create_problem(self, problem):
        """Factory creates a valid public problem."""
        assert problem.pk is not None
        assert problem.visibility == ProblemVisibility.PUBLIC

    def test_problem_str(self, problem):
        """__str__ returns 'code - name' format."""
        assert problem.code in str(problem)
        assert problem.name in str(problem)

    def test_is_public(self, problem):
        """Public visibility returns True for is_public."""
        assert problem.is_public is True

    def test_is_not_public(self):
        """Private visibility returns False for is_public."""
        problem = ProblemFactory(code="private1", visibility=ProblemVisibility.PRIVATE)
        assert problem.is_public is False

    def test_accessible_by_staff(self, problem):
        """Staff users can access private problems."""
        problem.visibility = ProblemVisibility.PRIVATE
        problem.save()

        staff = UserFactory(username="staff_access", is_staff=True)
        assert problem.is_accessible_by(staff) is True

    def test_accessible_by_anonymous(self, problem):
        """Public problems are accessible by anonymous users."""
        from django.contrib.auth.models import AnonymousUser

        assert problem.is_accessible_by(AnonymousUser()) is True

    def test_types_includes_standard(self, problem):
        """Default problem includes standard type."""
        assert "standard" in problem.types
