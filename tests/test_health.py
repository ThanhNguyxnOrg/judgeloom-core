from __future__ import annotations

from django.test import RequestFactory

from core.health import live, ready


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
