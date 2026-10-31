"""
JudgeLoom — Problem Tests
============================

Unit tests for Problem model properties and accessibility logic.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.services.auth_service import AuthService
from apps.problems.constants import ProblemVisibility
from apps.submissions.constants import SubmissionResult, SubmissionStatus
from tests.factories import ProblemFactory, SubmissionFactory, TagFactory, UserFactory


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


@pytest.mark.django_db
class TestProblemApi:
    def _client(self, user):
        client = Client()
        token = AuthService.generate_jwt_token(user)
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return client

    def test_jwt_author_can_read_private_problem(self):
        author = UserFactory()
        problem = ProblemFactory(code="private-jwt", visibility=ProblemVisibility.PRIVATE)
        problem.authors.add(author)

        response = self._client(author).get("/api/problems/private-jwt")
        assert response.status_code == 200

        response = self._client(UserFactory()).get("/api/problems/private-jwt")
        assert response.status_code == 403

    def test_jwt_user_can_create_problem(self):
        response = self._client(UserFactory()).post(
            "/api/problems/",
            data='{"code":"created-jwt","name":"Created","description":"desc","visibility":"private"}',
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["code"] == "created-jwt"

    def test_search_tag_source_ordering_and_solved_filters(self):
        user = UserFactory()
        tag = TagFactory(code="dp")
        matching = ProblemFactory(code="matching", name="Matching Problem", source="ICPC", points=100)
        matching.tags.add(tag)
        ProblemFactory(code="other", name="Other Problem", source="IOI", points=10)
        SubmissionFactory(
            user=user,
            problem=matching,
            result=SubmissionResult.AC,
            status=SubmissionStatus.COMPLETED,
        )

        client = self._client(user)
        response = client.get("/api/problems/?search=Matching&tag=dp&source=ICPC&ordering=-points")
        assert response.status_code == 200
        codes = [item["code"] for item in response.json()["results"]]
        assert codes == ["matching"]

        response = client.get("/api/problems/?solved=true")
        assert response.status_code == 200
        codes = [item["code"] for item in response.json()["results"]]
        assert codes == ["matching"]
