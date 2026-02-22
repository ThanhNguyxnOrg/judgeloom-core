"""
JudgeLoom — Submission Tests
================================

Unit tests for the Submission model, properties, and signals.
"""

from __future__ import annotations

import pytest

from apps.submissions.constants import SubmissionResult, SubmissionStatus
from tests.factories import SubmissionFactory


@pytest.mark.django_db
class TestSubmissionModel:
    """Tests for the Submission model."""

    def test_create_submission(self, submission):
        """Factory creates a valid queued submission."""
        assert submission.pk is not None
        assert submission.status == SubmissionStatus.QUEUED

    def test_submission_str(self, submission):
        """__str__ includes id and status."""
        result = str(submission)
        assert "Submission" in result
        assert submission.status in result

    def test_is_graded_false_when_queued(self, submission):
        """Queued submission is not graded."""
        assert submission.is_graded is False

    def test_is_graded_true_when_completed(self, submission):
        """Completed submission is graded."""
        submission.status = SubmissionStatus.COMPLETED
        assert submission.is_graded is True

    def test_is_graded_true_when_error(self, submission):
        """Error submission is graded."""
        submission.status = SubmissionStatus.ERROR
        assert submission.is_graded is True

    def test_result_class_default(self, submission):
        """No result yields secondary CSS class."""
        assert submission.result_class == "secondary"

    def test_result_class_accepted(self, submission):
        """AC result yields success CSS class."""
        submission.result = SubmissionResult.AC
        assert submission.result_class == "success"

    def test_memory_display_kb(self, submission):
        """Small memory displays in KB."""
        submission.memory_used = 512
        assert submission.memory_display == "512 KB"

    def test_memory_display_mb(self, submission):
        """Large memory displays in MB."""
        submission.memory_used = 2048
        assert "MB" in submission.memory_display

    def test_time_display_ms(self, submission):
        """Short time displays in ms."""
        submission.time_used = 0.5
        assert "ms" in submission.time_display

    def test_time_display_seconds(self, submission):
        """Long time displays in seconds."""
        submission.time_used = 1.234
        assert "s" in submission.time_display

    def test_score_percentage_ac(self, submission):
        """AC result with no points returns 100%."""
        submission.result = SubmissionResult.AC
        submission.points = 0.0
        assert submission.score_percentage == 100.0


@pytest.mark.django_db
class TestSubmissionSignals:
    """Tests for submission-related signals."""

    def test_user_stats_update_on_completed(self, user, problem, language):
        """Completing a submission updates user.problem_count."""
        sub = SubmissionFactory(
            user=user,
            problem=problem,
            language=language,
            status=SubmissionStatus.COMPLETED,
            result=SubmissionResult.AC,
            points=100.0,
        )
        user.refresh_from_db()
        assert user.problem_count >= 1
