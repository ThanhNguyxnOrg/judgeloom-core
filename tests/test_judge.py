"""
JudgeLoom — Judge Tests
==========================

Unit tests for the Judge and Language models.
"""

from __future__ import annotations

import pytest

from tests.factories import JudgeFactory, LanguageFactory


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
