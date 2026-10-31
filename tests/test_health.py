from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import RequestFactory

from core.health import live, ready


@pytest.mark.django_db
class TestHealthEndpoints:
    def test_live_endpoint_returns_ok(self) -> None:
        request = RequestFactory().get("/api/health/live")

        payload = live(request)

        assert payload["status"] == "ok"
        assert payload["check"] == "live"
        assert payload["service"] == "judgeloom-core"

    def test_ready_endpoint_returns_dependency_status(self) -> None:
        request = RequestFactory().get("/api/health/ready")

        payload = ready(request)

        assert payload["check"] == "ready"
        assert payload["service"] == "judgeloom-core"
        assert payload["status"] == "ok"
        dependencies = payload["dependencies"]
        assert isinstance(dependencies, dict)
        assert dependencies["database"] == "ok"

    def test_ready_endpoint_reports_database_failure(self) -> None:
        request = RequestFactory().get("/api/health/ready")

        with patch("core.health.connection.ensure_connection", side_effect=RuntimeError("down")):
            response = ready(request)

        assert response.status_code == 503
        assert b'"database": "error"' in response.content
