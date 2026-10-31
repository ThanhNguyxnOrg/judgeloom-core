from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from apps.contests.formats import register_format
from apps.contests.formats.base import AbstractContestFormat

if TYPE_CHECKING:
    from apps.contests.models import ContestParticipation, ContestProblem


class IOIFormatConfig(BaseModel):
    """Configuration schema for IOI format."""


@register_format
class IOIContestFormat(AbstractContestFormat):
    """IOI style: best score per subtask across submissions."""

    name = "IOI"
    key = "ioi"
    config_schema = IOIFormatConfig

    def calculate_participation(
        self,
        participation: ContestParticipation,
        freeze_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Calculate participation with IOI subtask aggregation."""

        total_score = 0.0
        problem_results: dict[str, dict[str, Any]] = {}

        for contest_problem in participation.contest.contest_problems.select_related("problem").all():
            result = self.get_problem_result(participation, contest_problem, freeze_time=freeze_time)
            total_score += float(result.get("points", 0.0))
            problem_results[contest_problem.label] = result

        return {
            "score": total_score,
            "tiebreaker": 0.0,
            "cumulative_time": timedelta(0),
            "format_data": {"problems": problem_results},
        }

    def get_problem_result(
        self,
        participation: ContestParticipation,
        contest_problem: ContestProblem,
        freeze_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute IOI best score for each subtask and sum."""

        submissions = list(self._submission_queryset(participation, contest_problem, freeze_time=freeze_time))
        attempts = len(submissions)
        best_subtasks: dict[str, float] = {}
        best_points = 0.0

        for submission in submissions:
            submission_subtasks = self._subtask_scores(submission)
            if submission_subtasks:
                for subtask, value in submission_subtasks.items():
                    best_subtasks[subtask] = max(best_subtasks.get(subtask, 0.0), value)
            else:
                best_points = max(best_points, self._points(submission))

        if best_subtasks:
            best_points = sum(best_subtasks.values())

        return {
            "points": best_points,
            "attempts": attempts,
            "subtasks": best_subtasks,
            "solved": best_points > 0,
        }
