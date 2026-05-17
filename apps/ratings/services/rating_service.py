from __future__ import annotations

import math
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.contests.models import Contest
from apps.contests.services.ranking_service import RankingService
from apps.ratings.models import Rating
from core import events as core_events


class RatingService:
    """Service for rating calculation and historical rating data."""

    @staticmethod
    @transaction.atomic
    def calculate_ratings(contest: Contest) -> list[Rating]:
        """Calculate and persist rating changes for a contest.

        Args:
            contest: Rated contest with finalized ranking.

        Returns:
            Created/updated rating rows.
        """

        ranking = RankingService.get_contest_ranking(contest)
        participants = [row for row in ranking if row.get("participation_id")]
        if not participants:
            return []

        user_model = get_user_model()
        users_by_id = {
            user.id: user for user in user_model.objects.filter(id__in=[entry["user_id"] for entry in participants])
        }

        contestants: list[dict[str, Any]] = []
        for entry in participants:
            user = users_by_id[entry["user_id"]]
            contestants.append(
                {
                    "user": user,
                    "user_id": user.id,
                    "participation_id": entry["participation_id"],
                    "rank": int(entry["rank"]),
                    "rating_before": int(getattr(user, "rating", RatingService._initial_rating())),
                    "score": float(entry["score"]),
                }
            )

        updates = RatingService._elo_update(contestants)
        rating_rows: list[Rating] = []

        participation_model = contest.participations.model

        for update in updates:
            user = update["user"]
            participation = participation_model.objects.get(pk=update["participation_id"])
            rating_row, _ = Rating.objects.update_or_create(
                user=user,
                contest=contest,
                defaults={
                    "participation": participation,
                    "rank": update["rank"],
                    "rating_before": update["rating_before"],
                    "rating_after": update["rating_after"],
                    "volatility_before": update["volatility_before"],
                    "volatility_after": update["volatility_after"],
                    "performance": update["performance"],
                },
            )
            rating_rows.append(rating_row)

            user.rating = update["rating_after"]
            user.max_rating = max(int(getattr(user, "max_rating", 0)), update["rating_after"])
            user.save(update_fields=["rating", "max_rating"])

            core_events.publish_sync(
                core_events.Event(
                    type=core_events.USER_RATING_CHANGED,
                    payload={
                        "user_id": user.id,
                        "contest_id": contest.id,
                        "rating_before": update["rating_before"],
                        "rating_after": update["rating_after"],
                        "delta": update["rating_after"] - update["rating_before"],
                    },
                )
            )

        return rating_rows

    @staticmethod
    def get_rating_history(user: Any) -> list[dict[str, Any]]:
        """Return ordered rating history for a user.

        Args:
            user: User instance.

        Returns:
            Serialized rating history entries.
        """

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
        """Return rating delta list for all users in a contest.

        Args:
            contest: Target contest.

        Returns:
            Serialized rating change rows.
        """

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
        initial = RatingService._initial_rating()
        floor = RatingService._rating_floor()

        user_model.objects.filter(ratings__isnull=False).update(rating=initial, max_rating=initial)
        Rating.objects.all().delete()

        contests = Contest.objects.filter(is_rated=True).order_by("end_time", "id")
        for contest in contests:
            _ = RatingService.calculate_ratings(contest)

        user_model.objects.filter(rating__lt=floor).update(rating=floor)

    @staticmethod
    def _elo_update(contestants: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compute single-contest Elo updates from ranking.

        Args:
            contestants: Ranked contestants with base ratings.

        Returns:
            Contestants list including rating transition fields.
        """

        if not contestants:
            return []

        n = len(contestants)
        k_base = 32.0

        for contestant in contestants:
            rating = float(contestant["rating_before"])
            rank = int(contestant["rank"])

            expected = 0.0
            actual = 0.0
            for opponent in contestants:
                if opponent is contestant:
                    continue
                opp_rating = float(opponent["rating_before"])
                expected += 1.0 / (1.0 + math.pow(10.0, (opp_rating - rating) / 400.0))

                if rank < int(opponent["rank"]):
                    actual += 1.0
                elif rank == int(opponent["rank"]):
                    actual += 0.5

            if n > 1:
                expected /= n - 1
                actual /= n - 1

            k = k_base * (1.25 if rating < 2000 else 1.0)
            delta = round(k * (actual - expected))
            rating_after = max(RatingService._rating_floor(), int(rating) + delta)
            performance = round(rating + 400.0 * (actual - expected))

            contestant["rating_after"] = rating_after
            contestant["volatility_before"] = 0
            contestant["volatility_after"] = abs(delta)
            contestant["performance"] = performance

        return contestants

    @staticmethod
    def _initial_rating() -> int:
        """Return configured initial rating."""

        return int(getattr(settings, "JUDGELOOM", {}).get("RATING_INITIAL", 1500))

    @staticmethod
    def _rating_floor() -> int:
        """Return configured rating floor."""

        return int(getattr(settings, "JUDGELOOM", {}).get("RATING_FLOOR", 0))
