from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.contests.models import Contest
from apps.contests.services.ranking_service import RankingService
from apps.ratings.services.rating_service import RatingService
from core.cache import invalidate_pattern
from core.events import CONTEST_ENDED, CONTEST_RANKING_UPDATED, CONTEST_STARTED, Event, publish_sync

logger = logging.getLogger(__name__)


class ContestLifecycleService:
    """Service layer for contest lifecycle orchestration."""

    @staticmethod
    @transaction.atomic
    def recalculate_rankings(contest_id: int) -> None:
        """Recalculate rankings for a contest and broadcast updates.

        Args:
            contest_id: Primary key of the target contest.
        """

        contest = Contest.objects.filter(id=contest_id).first()
        if contest is None:
            return

        RankingService.recalculate_contest(contest)
        invalidate_pattern("jl:contest:list")
        invalidate_pattern(f"jl:contest:{contest.id}")
        publish_sync(
            Event(
                type=CONTEST_RANKING_UPDATED,
                payload={"contest_id": contest.id, "contest_key": contest.key},
            )
        )

    @staticmethod
    @transaction.atomic
    def start_contest(contest_id: int) -> None:
        """Publish contest start side effects.

        Args:
            contest_id: Primary key of the target contest.
        """

        contest = Contest.objects.select_for_update().filter(id=contest_id).first()
        if contest is None or contest.started_at is not None:
            return

        contest.started_at = timezone.now()
        contest.save(update_fields=["started_at", "updated_at"])
        invalidate_pattern("jl:contest:list")
        invalidate_pattern(f"jl:contest:{contest.id}")
        publish_sync(
            Event(
                type=CONTEST_STARTED,
                payload={"contest_id": contest.id, "contest_key": contest.key},
            )
        )

    @staticmethod
    @transaction.atomic
    def end_contest(contest_id: int) -> None:
        """Finalize contest state and publish contest end side effects.

        Args:
            contest_id: Primary key of the target contest.
        """

        contest = Contest.objects.select_for_update().filter(id=contest_id).first()
        if contest is None or contest.ended_at is not None:
            return

        RankingService.recalculate_contest(contest)
        if contest.is_rated:
            RatingService.calculate_ratings(contest)
        contest.ended_at = timezone.now()
        contest.save(update_fields=["ended_at", "updated_at"])

        invalidate_pattern("jl:contest:list")
        invalidate_pattern(f"jl:contest:{contest.id}")
        publish_sync(
            Event(
                type=CONTEST_ENDED,
                payload={"contest_id": contest.id, "contest_key": contest.key},
            )
        )

    @staticmethod
    def tick_contests() -> dict[str, int]:
        """Start or end contests whose schedule has elapsed."""

        now = timezone.now()
        started = 0
        ended = 0

        for contest_id in Contest.objects.filter(
            started_at__isnull=True,
            start_time__lte=now,
        ).values_list("id", flat=True):
            try:
                ContestLifecycleService.start_contest(contest_id)
                started += 1
            except Exception:
                logger.exception("Failed to start contest %s", contest_id)

        for contest_id in Contest.objects.filter(
            ended_at__isnull=True,
            end_time__lte=now,
        ).values_list("id", flat=True):
            try:
                ContestLifecycleService.end_contest(contest_id)
                ended += 1
            except Exception:
                logger.exception("Failed to end contest %s", contest_id)

        return {"started": started, "ended": ended}
