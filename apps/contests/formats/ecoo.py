from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from apps.contests.formats import register_format
from apps.contests.formats.base import AbstractContestFormat

if TYPE_CHECKING:
    from apps.contests.models import ContestParticipation, ContestProblem


class ECOOFormatConfig(BaseModel):
    """Configuration schema for ECOO format."""

    tries_per_problem: int = Field(default=3, ge=1)


@register_format
class ECOOContestFormat(AbstractContestFormat):
    """ECOO style: fixed tries per problem and solved-count score."""

    name = "ECOO"
    key = "ecoo"
    config_schema = ECOOFormatConfig

    def update_participation(self, participation: ContestParticipation) -> None:
        """Recalculate ECOO participation score and details."""

        total_solved = 0
        per_problem: dict[str, dict[str, Any]] = {}

        for contest_problem in participation.contest.contest_problems.select_related("problem").all():
            result = self.get_problem_result(participation, contest_problem)
            per_problem[contest_problem.label] = result
            total_solved += int(result["solved"])

        participation.score = float(total_solved)
        participation.tiebreaker = 0.0
        participation.cumulative_time = timedelta(0)
        participation.format_data = {"problems": per_problem}
        participation.save(update_fields=["score", "tiebreaker", "cumulative_time", "format_data", "updated_at"])

    def get_problem_result(
        self,
        participation: ContestParticipation,
        contest_problem: ContestProblem,
    ) -> dict[str, Any]:
        """Compute ECOO result by evaluating limited tries."""

        cfg = self.validate_config(participation.contest.format_config)
        tries = list(self._submission_queryset(participation, contest_problem)[: cfg.tries_per_problem])
        solved = any(self._is_accepted(submission) for submission in tries)

        return {
            "points": 1.0 if solved else 0.0,
            "attempts": len(tries),
            "solved": solved,
            "tries_allowed": cfg.tries_per_problem,
        }
