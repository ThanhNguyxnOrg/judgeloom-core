from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from apps.contests.formats import register_format
from apps.contests.formats.base import AbstractContestFormat

if TYPE_CHECKING:
    from apps.contests.models import ContestParticipation, ContestProblem


class AtCoderFormatConfig(BaseModel):
    """Configuration schema for AtCoder format."""

    penalty_minutes: int = Field(default=5, ge=0)


@register_format
class AtCoderContestFormat(AbstractContestFormat):
    """AtCoder style: solved problem points and wrong-attempt penalty."""

    name = "AtCoder"
    key = "atcoder"
    config_schema = AtCoderFormatConfig

    def update_participation(self, participation: ContestParticipation) -> None:
        """Recalculate participation score and penalty in AtCoder mode."""

        cfg = self.validate_config(participation.contest.format_config)
        total_points = 0.0
        total_wrong = 0
        last_ac_minutes = 0
        per_problem: dict[str, dict[str, Any]] = {}

        for contest_problem in participation.contest.contest_problems.select_related("problem").all():
            result = self.get_problem_result(participation, contest_problem)
            per_problem[contest_problem.label] = result
            if bool(result["solved"]):
                total_points += float(contest_problem.points)
                total_wrong += int(result["wrong_attempts"])
                last_ac_minutes = max(last_ac_minutes, int(result["ac_minutes"]))

        penalty = last_ac_minutes + total_wrong * cfg.penalty_minutes
        participation.score = total_points
        participation.tiebreaker = float(penalty)
        participation.cumulative_time = timedelta(minutes=penalty)
        participation.format_data = {
            "penalty_minutes": cfg.penalty_minutes,
            "problems": per_problem,
        }
        participation.save(update_fields=["score", "tiebreaker", "cumulative_time", "format_data", "updated_at"])

    def get_problem_result(
        self,
        participation: ContestParticipation,
        contest_problem: ContestProblem,
    ) -> dict[str, Any]:
        """Compute solved state and wrong attempts before first AC."""

        wrong_attempts = 0
        solved = False
        ac_minutes = 0

        for submission in self._submission_queryset(participation, contest_problem):
            if self._is_accepted(submission):
                solved = True
                ac_minutes = int(self._submission_time_seconds(participation, submission) // 60)
                break
            wrong_attempts += 1

        return {
            "points": float(contest_problem.points) if solved else 0.0,
            "attempts": wrong_attempts + (1 if solved else 0),
            "wrong_attempts": wrong_attempts,
            "solved": solved,
            "ac_minutes": ac_minutes,
        }
