from __future__ import annotations

from celery import shared_task

from apps.contests.services.contest_lifecycle_service import ContestLifecycleService


@shared_task(
    bind=True,
    name="contests.recalculate_contest_rankings",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def recalculate_contest_rankings(self: object, contest_id: int) -> None:
    """Recalculate contest rankings and publish ranking update event.

    Args:
        self: Celery task instance.
        contest_id: Primary key of the contest to recalculate.
    """

    ContestLifecycleService.recalculate_rankings(contest_id)


@shared_task(
    bind=True,
    name="contests.schedule_contest_start",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def schedule_contest_start(self: object, contest_id: int) -> None:
    """Run side effects when a contest start schedule fires.

    Args:
        self: Celery task instance.
        contest_id: Primary key of the contest to start.
    """

    ContestLifecycleService.start_contest(contest_id)


@shared_task(
    bind=True,
    name="contests.schedule_contest_end",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def schedule_contest_end(self: object, contest_id: int) -> None:
    """Run side effects when a contest end schedule fires.

    Args:
        self: Celery task instance.
        contest_id: Primary key of the contest to finalize.
    """

    ContestLifecycleService.end_contest(contest_id)
