from __future__ import annotations

from celery import shared_task

from apps.contests.models import Contest
from apps.ratings.services.rating_service import RatingService


@shared_task(
    bind=True,
    name="ratings.recalculate_ratings_for_contest",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def recalculate_ratings_for_contest(self: object, contest_id: int) -> None:
    """Recalculate rating changes for one contest.

    Args:
        self: Celery task instance.
        contest_id: Primary key of the rated contest.
    """

    contest = Contest.objects.filter(id=contest_id).first()
    if contest is None:
        return

    RatingService.calculate_ratings(contest)


@shared_task(
    bind=True,
    name="ratings.recalculate_all_ratings",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def recalculate_all_ratings(self: object) -> None:
    """Recalculate all user ratings across all rated contests.

    Args:
        self: Celery task instance.
    """

    RatingService.recalculate_all_ratings()
