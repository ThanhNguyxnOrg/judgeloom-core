from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.services.auth_service import AuthService
from apps.problems.constants import ProblemVisibility
from tests.factories import AdminUserFactory, ProblemFactory, TagFactory, UserFactory


@pytest.mark.django_db
class TestTagApi:
    def _client(self, user):
        client = Client()
        token = AuthService.generate_jwt_token(user)
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return client

    def _tag_with_problems(self):
        tag = TagFactory(code="dp")
        public = ProblemFactory(code="tag-public", visibility=ProblemVisibility.PUBLIC)
        private = ProblemFactory(code="tag-private", visibility=ProblemVisibility.PRIVATE)
        public.tags.add(tag)
        private.tags.add(tag)
        return tag, public, private

    def test_jwt_user_sees_only_visible_problem_count(self):
        tag, _, _ = self._tag_with_problems()
        response = self._client(UserFactory()).get("/api/tags/")

        assert response.status_code == 200
        row = next(item for item in response.json() if item["code"] == tag.code)
        assert row["problem_count"] == 1

    def test_staff_sees_all_problem_counts(self):
        tag, _, _ = self._tag_with_problems()
        response = self._client(AdminUserFactory()).get("/api/tags/")

        assert response.status_code == 200
        row = next(item for item in response.json() if item["code"] == tag.code)
        assert row["problem_count"] == 2

    def test_tag_detail_filters_invisible_problems(self):
        tag, public, private = self._tag_with_problems()
        response = self._client(UserFactory()).get(f"/api/tags/{tag.code}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["problem_count"] == 1
        assert [item["code"] for item in payload["problems"]] == [public.code]
        assert private.code not in [item["code"] for item in payload["problems"]]

    def test_jwt_staff_can_create_tag_and_nonstaff_cannot(self):
        staff_response = self._client(AdminUserFactory()).post(
            "/api/tags/",
            data='{"name": "Graphs"}',
            content_type="application/json",
        )
        assert staff_response.status_code == 200
        assert staff_response.json()["code"] == "graphs"

        user_response = self._client(UserFactory()).post(
            "/api/tags/",
            data='{"name": "Trees"}',
            content_type="application/json",
        )
        assert user_response.status_code == 403
