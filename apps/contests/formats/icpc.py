from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel

from apps.contests.formats import register_format
from apps.contests.formats.base import AbstractContestFormat

if TYPE_CHECKING:
    from apps.contests.models import ContestParticipation, ContestProblem


class ICPCFormatConfig(BaseModel):
    """Configuration schema for ICPC format."""

    wrong_penalty_minutes: int = 20


@register_format
class ICPCContestFormat(AbstractContestFormat):
    """ICPC style: solved count + penalty time tie breaker."""

    name = "ICPC"
    key = "icpc"
    config_schema = ICPCFormatConfig

    def update_participation(self, participation: ContestParticipation) -> None:
        """Recalculate participation with ICPC solve/penalty rules."""

        cfg = self.validate_config(participation.contest.format_config)
        solved = 0
        penalty_minutes = 0
        per_problem: dict[str, dict[str, float | int | bool]] = {}

        for contest_problem in participation.contest.contest_problems.select_related("problem").all():
            result = self.get_problem_result(participation, contest_problem)
            solved += int(result["solved"])
            penalty_minutes += int(result["penalty_minutes"])
            per_problem[contest_problem.label] = result

        participation.score = float(solved)
        participation.tiebreaker = float(penalty_minutes)
        participation.cumulative_time = timedelta(minutes=penalty_minutes)
        participation.format_data = {
            "wrong_penalty_minutes": cfg.wrong_penalty_minutes,
            "problems": per_problem,
        }
        participation.save(update_fields=["score", "tiebreaker", "cumulative_time", "format_data", "updated_at"])

    def get_problem_result(
        self,
        participation: ContestParticipation,
        contest_problem: ContestProblem,
    ) -> dict[str, float | int | bool]:
        """Compute ICPC result for a single contest problem."""

        cfg = self.validate_config(participation.contest.format_config)
        wrong_attempts = 0
        solved = False
        solve_minutes = 0

        for submission in self._submission_queryset(participation, contest_problem):
            if self._is_accepted(submission):
                solved = True
                solve_minutes = int(self._submission_time_seconds(participation, submission) // 60)
                break
            wrong_attempts += 1

        penalty_minutes = solve_minutes + (wrong_attempts * cfg.wrong_penalty_minutes) if solved else 0
        return {
            "points": 1.0 if solved else 0.0,
            "attempts": wrong_attempts + (1 if solved else 0),
            "wrong_attempts": wrong_attempts,
            "solved": solved,
            "solve_minutes": solve_minutes,
            "penalty_minutes": penalty_minutes,
        }
