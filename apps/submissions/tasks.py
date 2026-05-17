from __future__ import annotations

from typing import Any, cast

from celery import shared_task

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


@shared_task(name="submissions.rejudge_submissions")
def rejudge_submissions(submission_ids: list[int]) -> None:
    """Queue multiple submissions for rejudging.

    Args:
        submission_ids: Submission ids to enqueue.
    """
    task = cast("Any", judge_submission)
    for submission_id in submission_ids:
        task.delay(submission_id)
