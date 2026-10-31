from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from celery import shared_task
from django.utils import timezone

from apps.submissions.constants import SubmissionMode
from core.exceptions import JudgeUnavailableError


@shared_task(name="submissions.judge_submission")
def judge_submission(submission_id: int) -> None:
    """Dispatch a submission to an available judge.

    Args:
        submission_id: Primary key of the submission to dispatch.

    Raises:
        JudgeUnavailableError: If no judge could accept the submission.
    """
    from apps.judge.bridge.bridge_manager import BridgeManager
    from apps.submissions.models import Submission

    submission = (
        Submission.objects.select_related("problem", "language")
        .prefetch_related("source")
        .filter(id=submission_id)
        .first()
    )
    if submission is None:
        return

    manager = BridgeManager.get_instance()
    dispatched = manager.dispatch_submission(submission)
    if not dispatched:
        raise JudgeUnavailableError("No available judge could accept the submission.")


@shared_task(name="submissions.cleanup_runs")
def cleanup_runs(ttl_minutes: int = 30) -> int:
    """Delete ephemeral run rows older than the retention window."""

    from apps.submissions.models import Submission

    cutoff = timezone.now() - timedelta(minutes=ttl_minutes)
    deleted, _ = Submission.objects.filter(
        mode=SubmissionMode.RUN,
        created_at__lt=cutoff,
    ).delete()
    return int(deleted)


@shared_task(name="submissions.rejudge_submissions")
def rejudge_submissions(submission_ids: list[int]) -> None:
    """Queue multiple submissions for rejudging.

    Args:
        submission_ids: Submission ids to enqueue.
    """
    task = cast("Any", judge_submission)
    for submission_id in submission_ids:
        task.delay(submission_id)
