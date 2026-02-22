from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.judge.models import Judge
from apps.judge.services.judge_service import JudgeService
from apps.submissions.constants import SubmissionStatus
from apps.submissions.models import Submission
from apps.submissions.services.submission_service import SubmissionService
from core.cache import invalidate_pattern


class JudgeMaintenanceService:
    """Maintenance operations for judge fleet health and stale sessions."""

    HEARTBEAT_TIMEOUT_SECONDS = 120

    @staticmethod
    def monitor_judges() -> int:
        """Mark stale judges offline based on their heartbeat timestamps.

        Returns:
            Number of judges transitioned to offline state.
        """

        timeout_at = timezone.now() - timedelta(seconds=JudgeMaintenanceService.HEARTBEAT_TIMEOUT_SECONDS)
        stale_judges = JudgeService.list_judges().filter(online=True, updated_at__lt=timeout_at)

        stale_count = 0
        for judge in stale_judges:
            if judge.online:
                judge.online = False
                judge.save(update_fields=["online", "updated_at"])
                stale_count += 1

        if stale_count:
            invalidate_pattern("jl:judge:list")
        return stale_count

    @staticmethod
    def cleanup_stale_sessions() -> int:
        """Requeue stale in-flight submissions tied to offline judges.

        Returns:
            Number of submissions requeued for rejudging.
        """

        stale_submissions = Submission.objects.select_related("judged_on", "problem", "language").filter(
            status__in=[SubmissionStatus.COMPILING, SubmissionStatus.JUDGING],
            judged_on__isnull=False,
            judged_on__online=False,
        )

        requeued = 0
        for submission in stale_submissions:
            SubmissionService.rejudge_submission(submission)
            requeued += 1
        return requeued
