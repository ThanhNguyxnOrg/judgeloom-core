from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction

from apps.contests.formats import get_format

if TYPE_CHECKING:
    from apps.contests.models import Contest, ContestParticipation


class RankingService:
    """Ranking orchestration service for contests."""

    @staticmethod
    def get_contest_ranking(contest: Contest) -> list[dict[str, Any]]:
        """Return ranking entries for a contest.

        Args:
            contest: Contest to rank.

        Returns:
            Ranking entries.
        """

        format_impl = get_format(contest.format_name)
        return format_impl.get_ranking(contest)

    @staticmethod
    @transaction.atomic
    def recalculate_participation(participation: ContestParticipation) -> None:
        """Recalculate score data for one participation.

        Args:
            participation: Participation to recompute.
        """

        format_impl = get_format(participation.contest.format_name)
        format_impl.update_participation(participation)

    @staticmethod
    @transaction.atomic
    def recalculate_contest(contest: Contest) -> None:
        """Recalculate all participations for a contest.

        Args:
            contest: Contest whose participations should be recalculated.
        """

        for participation in contest.participations.select_related("contest").all():
            RankingService.recalculate_participation(participation)

    @staticmethod
    def get_frozen_ranking(contest: Contest) -> list[dict[str, Any]]:
        """Return scoreboard with freeze-sensitive presentation.

        When freeze is active, per-problem format data is hidden while preserving
        rank order by currently stored participation aggregate metrics.

        Args:
            contest: Contest to rank.

        Returns:
            Ranking entries appropriate for freeze window display.
        """

        if not contest.is_frozen:
            return RankingService.get_contest_ranking(contest)

        freeze_time = contest.start_time + contest.scoreboard_frozen_after
        format_impl = get_format(contest.format_name)
        entries: list[dict[str, Any]] = []

        for participation in contest.participations.select_related("user").filter(is_disqualified=False):
            frozen = format_impl.calculate_participation(participation, freeze_time=freeze_time)
            entries.append(
                {
                    "participation_id": participation.id,
                    "user_id": participation.user_id,
                    "username": getattr(participation.user, "username", str(participation.user_id)),
                    "score": float(frozen["score"]),
                    "tiebreaker": float(frozen["tiebreaker"]),
                    "cumulative_time": frozen["cumulative_time"],
                    "format_data": {"frozen": True},
                }
            )

        entries.sort(key=lambda item: (-item["score"], item["tiebreaker"], item["user_id"]))
        for rank, entry in enumerate(entries, start=1):
            entry["rank"] = rank
        return entries
