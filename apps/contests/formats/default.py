from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from apps.contests.formats import register_format
from apps.contests.formats.base import AbstractContestFormat

if TYPE_CHECKING:
    from apps.contests.models import ContestParticipation, ContestProblem


class DefaultFormatConfig(BaseModel):
    """Configuration schema for default format."""


@register_format
class DefaultContestFormat(AbstractContestFormat):
    """Best-score-per-problem format with sum scoring."""

    name = "Default"
    key = "default"
    config_schema = DefaultFormatConfig

    def calculate_participation(
        self,
        participation: ContestParticipation,
        freeze_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Calculate score using best submission per problem."""

        total_score = 0.0
        last_ac_seconds = 0.0
        cumulative_time = timedelta(0)
        problem_results: dict[str, dict[str, Any]] = {}

        for contest_problem in participation.contest.contest_problems.select_related("problem").all():
            result = self.get_problem_result(participation, contest_problem, freeze_time=freeze_time)
            total_score += float(result.get("points", 0.0))
            ac_seconds = float(result.get("ac_seconds", 0.0))
            if ac_seconds > 0:
                last_ac_seconds = max(last_ac_seconds, ac_seconds)
                cumulative_time = timedelta(seconds=last_ac_seconds)
            problem_results[contest_problem.label] = result

        return {
            "score": total_score,
            "tiebreaker": last_ac_seconds,
            "cumulative_time": cumulative_time,
            "format_data": {"problems": problem_results},
        }

    def get_problem_result(
        self,
        participation: ContestParticipation,
        contest_problem: ContestProblem,
        freeze_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute best points and attempt information for one problem."""

        submissions = list(self._submission_queryset(participation, contest_problem, freeze_time=freeze_time))
        attempts = len(submissions)
        best_points = 0.0
        ac_seconds = 0.0

        for submission in submissions:
            points = self._points(submission)
            if points > best_points:
                best_points = points
            if self._is_accepted(submission):
                ac_seconds = max(ac_seconds, self._submission_time_seconds(participation, submission))

        return {
            "points": best_points,
            "attempts": attempts,
            "ac_seconds": ac_seconds,
            "solved": ac_seconds > 0,
        }
