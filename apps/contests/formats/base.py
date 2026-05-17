from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.utils import timezone
from pydantic import BaseModel

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet

    from apps.contests.models import Contest, ContestParticipation, ContestProblem


class EmptyConfig(BaseModel):
    """Default empty config model."""


class AbstractContestFormat(ABC):
    """Base API for all contest scoring format implementations."""

    name: str = "Base"
    key: str = "base"
    config_schema: type[BaseModel] = EmptyConfig

    @classmethod
    def validate_config(cls, raw_config: dict[str, Any]) -> BaseModel:
        """Validate and parse format config.

        Args:
            raw_config: Raw JSON config from contest model.

        Returns:
            Parsed pydantic model instance.
        """

        return cls.config_schema.model_validate(raw_config or {})

    @abstractmethod
    def update_participation(self, participation: ContestParticipation) -> None:
        """Recalculate and persist a participation's score and tie data.

        Args:
            participation: Participation entry to update.
        """

    def get_ranking(self, contest: Contest) -> list[dict[str, Any]]:
        """Build and sort ranking entries for a contest.

        Args:
            contest: Contest to rank.

        Returns:
            Sorted ranking entries.
        """

        entries: list[dict[str, Any]] = []
        queryset = contest.participations.select_related("user").filter(is_disqualified=False)
        for participation in queryset:
            entries.append(
                {
                    "participation_id": participation.id,
                    "user_id": participation.user_id,
                    "username": getattr(participation.user, "username", str(participation.user_id)),
                    "score": float(participation.score),
                    "tiebreaker": float(participation.tiebreaker),
                    "cumulative_time": participation.cumulative_time,
                    "format_data": participation.format_data,
                }
            )
        entries.sort(key=lambda item: (-item["score"], item["tiebreaker"], item["user_id"]))
        for rank, entry in enumerate(entries, start=1):
            entry["rank"] = rank
        return entries

    @abstractmethod
    def get_problem_result(
        self,
        participation: ContestParticipation,
        contest_problem: ContestProblem,
    ) -> dict[str, Any]:
        """Compute per-problem result for one participation.

        Args:
            participation: Participation entry.
            contest_problem: Contest problem relation.

        Returns:
            Result payload containing score/time/attempt stats.
        """

    def display_result(self, result: dict[str, Any]) -> str:
        """Return human-readable representation of result payload.

        Args:
            result: Result dictionary.

        Returns:
            Rendered text representation.
        """

        points = float(result.get("points", 0.0))
        attempts = int(result.get("attempts", 0))
        return f"{points:.2f} pts ({attempts} tries)"

    def _submission_queryset(
        self,
        participation: ContestParticipation,
        contest_problem: ContestProblem,
        *,
        freeze_time: datetime | None = None,
    ) -> QuerySet[Model]:
        """Return a submissions queryset constrained to participation/problem.

        This method builds filters dynamically to remain compatible with differing
        submission model schemas.

        Args:
            participation: Participation to load submissions for.
            contest_problem: Problem mapping in the contest.
            freeze_time: Optional upper timestamp bound.

        Returns:
            Queryset for matching submissions.
        """

        submission_model = apps.get_model("submissions", "Submission")
        queryset: QuerySet[Model] = submission_model.objects.all()
        field_names = {field.name for field in submission_model._meta.get_fields()}  # type: ignore[attr-defined]

        filters: dict[str, Any] = {}
        if "participation" in field_names:
            filters["participation_id"] = participation.id
        if "contest" in field_names:
            filters["contest_id"] = participation.contest_id
        if "contest_problem" in field_names:
            filters["contest_problem_id"] = contest_problem.id
        if "user" in field_names:
            filters["user_id"] = participation.user_id
        if "problem" in field_names:
            filters["problem_id"] = contest_problem.problem_id

        if filters:
            queryset = queryset.filter(**filters)

        if freeze_time and "created_at" in field_names:
            queryset = queryset.filter(created_at__lte=freeze_time)

        queryset = queryset.order_by("created_at", "id") if "created_at" in field_names else queryset.order_by("id")
        return queryset

    def _is_accepted(self, submission: Model) -> bool:
        """Infer accepted status from common submission attributes."""

        for attr in ("is_accepted", "accepted"):
            value = getattr(submission, attr, None)
            if isinstance(value, bool):
                return value

        verdict = str(getattr(submission, "verdict", "")).lower()
        status = str(getattr(submission, "status", "")).lower()
        token = verdict or status
        return token in {"ac", "accepted", "ok", "correct"}

    def _points(self, submission: Model) -> float:
        """Extract numeric points from common submission attributes."""

        for attr in ("points", "score", "total_points"):
            value = getattr(submission, attr, None)
            if isinstance(value, (int, float)):
                return float(value)
        return 0.0

    def _submission_time_seconds(self, participation: ContestParticipation, submission: Model) -> float:
        """Return elapsed seconds from participation start to submission time."""

        submitted_at = getattr(submission, "created_at", None)
        if not isinstance(submitted_at, datetime):
            submitted_at = timezone.now()
        start = participation.virtual_start or participation.contest.start_time
        return max((submitted_at - start).total_seconds(), 0.0)

    def _subtask_scores(self, submission: Model) -> dict[str, float]:
        """Extract subtask score mapping from submission payload."""

        payload = getattr(submission, "subtask_scores", None)
        if isinstance(payload, dict):
            return {str(k): float(v) for k, v in payload.items() if isinstance(v, (int, float))}

        result = getattr(submission, "result", None)
        if isinstance(result, dict):
            subtasks = result.get("subtasks")
            if isinstance(subtasks, dict):
                return {str(k): float(v) for k, v in subtasks.items() if isinstance(v, (int, float))}
        return {}
