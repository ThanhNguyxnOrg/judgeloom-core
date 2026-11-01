from __future__ import annotations

import pytest

from apps.accounts.services.auth_service import AuthService
from tests.factories import SubmissionFactory


@pytest.mark.django_db
def test_jwt_can_list_own_submissions(client, user):
    submission = SubmissionFactory(user=user)
    token = AuthService.generate_jwt_token(user)

    response = client.get("/api/submissions/", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == submission.id


@pytest.mark.django_db
def test_jwt_can_read_private_submission_detail(client, user):
    submission = SubmissionFactory(user=user, is_public=False)
    token = AuthService.generate_jwt_token(user)

    response = client.get(f"/api/submissions/{submission.id}", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 200
    assert response.json()["id"] == submission.id
