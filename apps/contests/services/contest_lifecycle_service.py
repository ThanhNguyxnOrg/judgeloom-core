from __future__ import annotations

from django.db import transaction

from apps.contests.models import Contest
from apps.contests.services.ranking_service import RankingService
from apps.ratings.services.rating_service import RatingService
from core.cache import invalidate_pattern
from core.events import CONTEST_ENDED, CONTEST_RANKING_UPDATED, CONTEST_STARTED, Event, publish_sync


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

        contest = Contest.objects.filter(id=contest_id).first()
        if contest is None:
            return

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

        contest = Contest.objects.filter(id=contest_id).first()
        if contest is None:
            return

        RankingService.recalculate_contest(contest)
        if contest.is_rated:
            RatingService.calculate_ratings(contest)

        invalidate_pattern("jl:contest:list")
        invalidate_pattern(f"jl:contest:{contest.id}")
        publish_sync(
            Event(
                type=CONTEST_ENDED,
                payload={"contest_id": contest.id, "contest_key": contest.key},
            )
        )
