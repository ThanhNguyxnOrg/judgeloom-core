from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.contests.constants import ParticipationStatus
from apps.contests.models import Contest
from apps.contests.services.ranking_service import RankingService
from apps.ratings.models import Rating
from apps.ratings.services import elo_mmr
from core import events as core_events


class RatingService:
    """Service for Elo-MMR rating calculation and historical rating data."""

    @staticmethod
    @transaction.atomic
    def calculate_ratings(contest: Contest, *, force: bool = False) -> list[Rating]:
        """Calculate and persist Elo-MMR rating changes for a contest.

        Args:
            contest: Rated contest with finalized ranking.
            force: Recompute an existing contest rating instead of returning it.

        Returns:
            Created/updated rating rows.
        """

        if not contest.is_rated:
            return []

        existing_rows = list(Rating.objects.filter(contest=contest).select_related("user").order_by("rank", "user_id"))
        if existing_rows and not force:
            return existing_rows

        excluded_user_ids = set(contest.rate_exclude.values_list("id", flat=True))
        participations = {
            participation.id: participation
            for participation in contest.participations.select_related("user").filter(
                is_disqualified=False,
                status=ParticipationStatus.LIVE,
            )
        }

        selected: list[dict[str, Any]] = []
        for entry in RankingService.get_contest_ranking(contest):
            participation = participations.get(entry.get("participation_id"))
            if participation is None or participation.user_id in excluded_user_ids:
                continue
            if not contest.rate_all and not participation.submissions.exists():
                continue

            user = participation.user
            history = list(
                Rating.objects.filter(user=user)
                .exclude(contest=contest)
                .select_related("contest")
                .order_by("-contest__end_time", "-id")
            )
            last = history[0] if history else None
            last_rating = last.rating_after if last is not None else elo_mmr.RATING_INIT
            if contest.rating_floor is not None and last_rating < contest.rating_floor:
                continue
            if contest.rating_ceiling is not None and last_rating > contest.rating_ceiling:
                continue

            selected.append(
                {
                    "user": user,
                    "participation_id": participation.id,
                    "rank_key": (float(entry["score"]), float(entry.get("tiebreaker", 0.0))),
                    "rating_before": last_rating,
                    "mean_before": last.mean if last is not None else elo_mmr.MEAN_INIT,
                    "historical": [float(row.performance) for row in history],
                    "times_ranked": len(history),
                }
            )

        if not selected:
            Rating.objects.filter(contest=contest).delete()
            return []

        ranks = RatingService._tie_ranks(selected)
        displayed, means, performances = elo_mmr.recalculate(
            ranks,
            [item["mean_before"] for item in selected],
            [item["times_ranked"] for item in selected],
            [item["historical"] for item in selected],
        )

        if force:
            Rating.objects.filter(contest=contest).delete()

        participation_model = contest.participations.model
        rating_rows: list[Rating] = []

        for index, item in enumerate(selected):
            user = item["user"]
            participation = participation_model.objects.get(pk=item["participation_id"])
            rating_after = min(
                RatingService._rating_ceiling(),
                max(RatingService._rating_floor(), displayed[index]),
            )
            times_ranked = item["times_ranked"]
            rating_row, _ = Rating.objects.update_or_create(
                user=user,
                contest=contest,
                defaults={
                    "participation": participation,
                    "rank": max(1, round(ranks[index] + 1)),
                    "rating_before": item["rating_before"],
                    "rating_after": rating_after,
                    "mean": means[index],
                    "volatility_before": round(elo_mmr.variance_for(times_ranked) ** 0.5),
                    "volatility_after": round(elo_mmr.variance_for(times_ranked + 1) ** 0.5),
                    "performance": performances[index],
                },
            )
            rating_rows.append(rating_row)

            user.rating = rating_after
            user.max_rating = max(int(getattr(user, "max_rating", 0)), rating_after)
            user.save(update_fields=["rating", "max_rating"])

            core_events.publish_sync(
                core_events.Event(
                    type=core_events.USER_RATING_CHANGED,
                    payload={
                        "user_id": user.id,
                        "contest_id": contest.id,
                        "rating_before": item["rating_before"],
                        "rating_after": rating_after,
                        "delta": rating_after - item["rating_before"],
                    },
                )
            )

        return rating_rows

    @staticmethod
    def _tie_ranks(selected: list[dict[str, Any]]) -> list[float]:
        """Assign half-step ranks to equal score/tiebreaker groups."""

        ranks: list[float] = []
        index = 0
        while index < len(selected):
            end = index + 1
            while end < len(selected) and selected[end]["rank_key"] == selected[index]["rank_key"]:
                end += 1
            average_rank = index + (end - index - 1) / 2.0
            ranks.extend([average_rank] * (end - index))
            index = end
        return ranks

    @staticmethod
    def get_rating_history(user: Any) -> list[dict[str, Any]]:
        """Return ordered rating history for a user."""

        return [
            {
                "contest_key": row.contest.key,
                "contest_name": row.contest.name,
                "rank": row.rank,
                "rating_before": row.rating_before,
                "rating_after": row.rating_after,
                "delta": row.rating_after - row.rating_before,
                "created_at": row.created_at,
            }
            for row in user.ratings.select_related("contest").order_by("created_at")
        ]

    @staticmethod
    def get_contest_rating_changes(contest: Contest) -> list[dict[str, Any]]:
        """Return rating delta list for all users in a contest."""

        return [
            {
                "user_id": row.user_id,
                "username": getattr(row.user, "username", str(row.user_id)),
                "rank": row.rank,
                "rating_before": row.rating_before,
                "rating_after": row.rating_after,
                "delta": row.rating_after - row.rating_before,
                "performance": row.performance,
            }
            for row in contest.ratings.select_related("user").order_by("rank", "user_id")
        ]

    @staticmethod
    @transaction.atomic
    def recalculate_all_ratings() -> None:
        """Recalculate all ratings from scratch in contest chronological order."""

        user_model = get_user_model()
        floor = RatingService._rating_floor()

        user_model.objects.filter(ratings__isnull=False).update(
            rating=elo_mmr.RATING_INIT,
            max_rating=elo_mmr.RATING_INIT,
        )
        Rating.objects.all().delete()

        for contest in Contest.objects.filter(is_rated=True).order_by("end_time", "id"):
            RatingService.calculate_ratings(contest)

        user_model.objects.filter(rating__lt=floor).update(rating=floor)

    @staticmethod
    def _initial_rating() -> int:
        """Return configured initial rating."""

        return int(getattr(settings, "JUDGELOOM", {}).get("RATING_INITIAL", elo_mmr.RATING_INIT))

    @staticmethod
    def _rating_floor() -> int:
        """Return configured rating floor."""

        return int(getattr(settings, "JUDGELOOM", {}).get("RATING_FLOOR", 0))

    @staticmethod
    def _rating_ceiling() -> int:
        """Return configured rating ceiling."""

        return int(getattr(settings, "JUDGELOOM", {}).get("RATING_CEILING", 4000))
