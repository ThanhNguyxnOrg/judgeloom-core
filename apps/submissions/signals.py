"""
JudgeLoom — Submission Signals
================================

Post-save and post-delete handlers that synchronize user statistics
and invalidate caches whenever a submission reaches a terminal state.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.models import Submission
from core.cache import invalidate_pattern, make_key

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Submission)
def update_user_stats_on_completion(
    sender: type[Submission],
    instance: Submission,
    created: bool,
    **kwargs: Any,
) -> None:
    """Recalculate user problem_count and points when a submission completes.

    Only fires when the submission transitions to COMPLETED status, to
    avoid unnecessary writes on intermediate status updates (QUEUED,
    COMPILING, JUDGING).

    Args:
        sender: The Submission model class.
        instance: The submission that was saved.
        created: Whether this is a new row.
        **kwargs: Extra signal keyword arguments.
    """
    if instance.status != SubmissionStatus.COMPLETED:
        return

    user = instance.user
    accepted_submissions = Submission.objects.filter(
        user=user,
        status=SubmissionStatus.COMPLETED,
        result=SubmissionResult.AC,
    )

    problem_count = (
        accepted_submissions.values("problem_id").distinct().count()
    )

    points_aggregate = (
        accepted_submissions.values("problem_id")
        .annotate(best=Sum("points"))
        .aggregate(total=Sum("best"))
    )
    total_points = points_aggregate.get("total") or 0.0

    type(user).objects.filter(pk=user.pk).update(
        problem_count=problem_count,
        points=total_points,
    )

    invalidate_pattern(make_key("user", user.pk))
    logger.debug(
        "Updated stats for user %s: problems=%d, points=%.2f",
        user.pk,
        problem_count,
        total_points,
    )


@receiver(post_delete, sender=Submission)
def invalidate_problem_stats_on_delete(
    sender: type[Submission],
    instance: Submission,
    **kwargs: Any,
) -> None:
    """Invalidate problem statistics cache when a submission is deleted.

    Args:
        sender: The Submission model class.
        instance: The submission being deleted.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("problem", instance.problem_id))
    logger.debug(
        "Invalidated problem stats cache for problem %s after submission delete",
        instance.problem_id,
    )
