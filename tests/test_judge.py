"""
JudgeLoom — Judge Tests
==========================

Unit tests for the Judge and Language models.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client

from apps.judge.models import Judge
from tests.factories import JudgeFactory


@pytest.mark.django_db
class TestLanguageModel:
    """Tests for the Language model."""

    def test_create_language(self, language):
        """Factory creates a valid Python language."""
        assert language.pk is not None
        assert language.key == "PY3"
        assert language.is_enabled is True

    def test_language_str(self, language):
        """__str__ returns the language key."""
        assert str(language) == "PY3"


@pytest.mark.django_db
class TestJudgeModel:
    """Tests for the Judge model."""

    def test_create_judge(self, judge):
        """Factory creates a valid online judge."""
        assert judge.pk is not None
        assert judge.online is True

    def test_judge_str(self, judge):
        """__str__ returns the judge name."""
        assert str(judge) == judge.name

    def test_status_available(self, judge):
        """Online, unblocked judge has AV status."""
        assert judge.status == "AV"

    def test_status_offline(self, judge):
        """Offline judge has OF status."""
        judge.online = False
        assert judge.status == "OF"

    def test_status_blocked(self, judge):
        """Blocked judge has DI status."""
        judge.is_blocked = True
        assert judge.status == "DI"

    def test_status_busy(self, judge):
        """High-load judge has BU status."""
        judge.load = 0.95
        assert judge.status == "BU"

    def test_uptime_none_without_start(self):
        """Uptime is None when start_time is not set."""
        judge = JudgeFactory(start_time=None)
        assert judge.uptime is None

    def test_create_judge_token_command(self):
        output = StringIO()

        call_command("create_judge_token", "token-command-judge", stdout=output)

        judge = Judge.objects.get(name="token-command-judge")
        assert judge.token_hash
        assert judge.token_prefix
        assert judge.auth_key == ""
        assert "Token (shown once):" in output.getvalue()


@pytest.mark.django_db
class TestJudgeMetrics:
    def test_metrics_require_staff(self, user):
        client = Client()
        client.force_login(user)
        assert client.get("/api/judge/metrics").status_code == 403

    def test_metrics_report_judge_and_queue_state(self, admin_user):
        JudgeFactory(online=True, is_blocked=False)
        JudgeFactory(online=False, is_blocked=True)
        client = Client()
        client.force_login(admin_user)

        response = client.get("/api/judge/metrics")
        assert response.status_code == 200
        payload = response.json()
        assert payload["online_judges"] == 1
        assert payload["blocked_judges"] == 1
        assert payload["queued"] == 0
        assert payload["oldest_queued_seconds"] == 0
        assert payload["leases_expiring_60s"] == 0
