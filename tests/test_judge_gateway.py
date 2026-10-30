from __future__ import annotations

import hashlib
import json

import pytest
from django.test import Client

from tests.factories import JudgeFactory


def auth_header(token: str = "secret") -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.mark.django_db
class TestJudgeTokenAuth:
    def test_heartbeat_accepts_valid_token_and_updates_judge(self):
        judge = JudgeFactory(
            name="gateway-heartbeat",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
            online=False,
        )
        client = Client()

        response = client.post(
            "/api/v1/judge/heartbeat",
            data=json.dumps({"load": 0.25, "running_jobs": 1}),
            content_type="application/json",
            **auth_header(),
        )

        assert response.status_code == 200
        judge.refresh_from_db()
        assert judge.last_seen is not None
        assert judge.online is True
        assert judge.current_load == 0.25
        assert judge.load == 0.25

    def test_heartbeat_rejects_wrong_token(self):
        JudgeFactory(name="gateway-wrong-token", token_hash=hashlib.sha256(b"secret").hexdigest())
        client = Client()

        response = client.post(
            "/api/v1/judge/heartbeat",
            data=json.dumps({"load": 0.1}),
            content_type="application/json",
            **auth_header("wrong"),
        )

        assert response.status_code == 401

    def test_heartbeat_rejects_blocked_judge(self):
        JudgeFactory(
            name="gateway-blocked",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
            is_blocked=True,
        )
        client = Client()

        response = client.post(
            "/api/v1/judge/heartbeat",
            data=json.dumps({"load": 0.1}),
            content_type="application/json",
            **auth_header(),
        )

        assert response.status_code == 403

    def test_register_persists_protocol_and_capabilities(self):
        judge = JudgeFactory(
            name="gateway-register",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
            online=False,
        )
        client = Client()

        response = client.post(
            "/api/v1/judge/register",
            data=json.dumps(
                {
                    "protocol_version": 1,
                    "capabilities": {"languages": ["PY3"], "sandbox": "go-judge"},
                }
            ),
            content_type="application/json",
            **auth_header(),
        )

        assert response.status_code == 200
        judge.refresh_from_db()
        assert judge.protocol_version == 1
        assert judge.capabilities == {"languages": ["PY3"], "sandbox": "go-judge"}
        assert judge.online is True
        assert judge.last_seen is not None
