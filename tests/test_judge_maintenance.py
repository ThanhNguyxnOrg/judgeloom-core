from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.judge.services.judge_maintenance_service import JudgeMaintenanceService
from apps.judge.tasks import cleanup_stale_sessions, monitor_judges
from apps.submissions.constants import SubmissionStatus
from tests.factories import JudgeFactory, SubmissionFactory

pytestmark = pytest.mark.django_db


class TestMonitorJudgesTask:
    def test_monitor_judges_marks_stale_judges_offline(self):
        threshold = timezone.now() - timedelta(seconds=JudgeMaintenanceService.HEARTBEAT_TIMEOUT_SECONDS + 10)
        stale_judge = JudgeFactory(online=True)
        stale_judge.__class__.objects.filter(id=stale_judge.id).update(updated_at=threshold)
        fresh_judge = JudgeFactory(online=True)

        offline_count = JudgeMaintenanceService.monitor_judges()

        assert offline_count == 1
        stale_judge.refresh_from_db()
        fresh_judge.refresh_from_db()
        assert stale_judge.online is False
        assert fresh_judge.online is True

    def test_monitor_judges_returns_zero_when_all_fresh(self):
        JudgeFactory(online=True)
        JudgeFactory(online=True)

        offline_count = JudgeMaintenanceService.monitor_judges()

        assert offline_count == 0

    def test_monitor_judges_ignores_already_offline_judges(self):
        threshold = timezone.now() - timedelta(seconds=JudgeMaintenanceService.HEARTBEAT_TIMEOUT_SECONDS + 10)
        already_offline = JudgeFactory(online=False)
        already_offline.__class__.objects.filter(id=already_offline.id).update(updated_at=threshold)

        offline_count = JudgeMaintenanceService.monitor_judges()

        assert offline_count == 0

    @patch("apps.judge.services.judge_maintenance_service.invalidate_pattern")
    def test_monitor_judges_invalidates_cache_when_changes_occur(self, mock_invalidate):
        threshold = timezone.now() - timedelta(seconds=JudgeMaintenanceService.HEARTBEAT_TIMEOUT_SECONDS + 10)
        stale_judge = JudgeFactory(online=True)
        stale_judge.__class__.objects.filter(id=stale_judge.id).update(updated_at=threshold)

        JudgeMaintenanceService.monitor_judges()

        mock_invalidate.assert_called_once_with("jl:judge:list")

    def test_monitor_judges_celery_task_delegates_to_service(self):
        threshold = timezone.now() - timedelta(seconds=JudgeMaintenanceService.HEARTBEAT_TIMEOUT_SECONDS + 10)
        stale_judge = JudgeFactory(online=True)
        stale_judge.__class__.objects.filter(id=stale_judge.id).update(updated_at=threshold)

        result = monitor_judges()

        assert result == 1


class TestCleanupStaleSessionsTask:
    @patch("apps.judge.services.judge_maintenance_service.SubmissionService.rejudge_submission")
    def test_cleanup_requeues_stale_compiling_submissions(self, mock_rejudge):
        offline_judge = JudgeFactory(online=False)
        stale_submission = SubmissionFactory(status=SubmissionStatus.COMPILING, judged_on=offline_judge)

        requeued_count = JudgeMaintenanceService.cleanup_stale_sessions()

        assert requeued_count == 1
        mock_rejudge.assert_called_once()
        called_submission = mock_rejudge.call_args[0][0]
        assert called_submission.id == stale_submission.id

    @patch("apps.judge.services.judge_maintenance_service.SubmissionService.rejudge_submission")
    def test_cleanup_requeues_stale_judging_submissions(self, mock_rejudge):
        offline_judge = JudgeFactory(online=False)
        stale_submission = SubmissionFactory(status=SubmissionStatus.JUDGING, judged_on=offline_judge)

        requeued_count = JudgeMaintenanceService.cleanup_stale_sessions()

        assert requeued_count == 1
        mock_rejudge.assert_called_once()
        called_submission = mock_rejudge.call_args[0][0]
        assert called_submission.id == stale_submission.id

    @patch("apps.judge.services.judge_maintenance_service.SubmissionService.rejudge_submission")
    def test_cleanup_ignores_submissions_on_online_judges(self, mock_rejudge):
        online_judge = JudgeFactory(online=True)
        active_submission = SubmissionFactory(status=SubmissionStatus.JUDGING, judged_on=online_judge)

        requeued_count = JudgeMaintenanceService.cleanup_stale_sessions()

        assert requeued_count == 0
        active_submission.refresh_from_db()
        assert active_submission.status == SubmissionStatus.JUDGING
        mock_rejudge.assert_not_called()

    @patch("apps.judge.services.judge_maintenance_service.SubmissionService.rejudge_submission")
    def test_cleanup_ignores_completed_submissions(self, mock_rejudge):
        offline_judge = JudgeFactory(online=False)
        completed_submission = SubmissionFactory(status=SubmissionStatus.COMPLETED, judged_on=offline_judge)

        requeued_count = JudgeMaintenanceService.cleanup_stale_sessions()

        assert requeued_count == 0
        completed_submission.refresh_from_db()
        assert completed_submission.status == SubmissionStatus.COMPLETED
        mock_rejudge.assert_not_called()

    @patch("apps.judge.services.judge_maintenance_service.SubmissionService.rejudge_submission")
    def test_cleanup_ignores_submissions_without_judge(self, mock_rejudge):
        queued_submission = SubmissionFactory(status=SubmissionStatus.QUEUED, judged_on=None)

        requeued_count = JudgeMaintenanceService.cleanup_stale_sessions()

        assert requeued_count == 0
        queued_submission.refresh_from_db()
        assert queued_submission.status == SubmissionStatus.QUEUED
        mock_rejudge.assert_not_called()

    @patch("apps.judge.services.judge_maintenance_service.SubmissionService.rejudge_submission")
    def test_cleanup_celery_task_delegates_to_service(self, mock_rejudge):
        offline_judge = JudgeFactory(online=False)
        SubmissionFactory(status=SubmissionStatus.JUDGING, judged_on=offline_judge)

        result = cleanup_stale_sessions()

        assert result == 1
        mock_rejudge.assert_called_once()
