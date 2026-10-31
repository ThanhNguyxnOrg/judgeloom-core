from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from apps.submissions.constants import SubmissionResult, SubmissionStatus

if TYPE_CHECKING:
    from apps.problems.models import ProblemPackage


@dataclass(frozen=True)
class ScoreSummary:
    points: float
    subtask_scores: dict[str, float]
    result: str
    status: str
    case_total: int
    case_passed: int
    time_used: float = 0.0
    memory_used: int = 0


class ScoringService:
    """Server-authoritative scoring over package case/group definitions."""

    @staticmethod
    def score(package: ProblemPackage, cases: list[dict[str, Any]]) -> ScoreSummary:
        """Recompute a submission score from per-case judge results.

        Args:
            package: Package that owns the immutable case/group definitions.
            cases: Per-case results reported by the worker.

        Returns:
            Aggregated score summary.
        """

        manifest = package.manifest or {}
        manifest_cases = manifest.get("cases") or []
        case_by_number = {index: case for index, case in enumerate(manifest_cases, start=1)}
        groups = manifest.get("groups") or [
            {
                "id": "default",
                "points": sum(float(case.get("points", 0) or 0) for case in manifest_cases),
                "mode": "sum",
            }
        ]
        group_defs = {str(group.get("id", "default")): group for group in groups}

        case_scores: dict[str, list[float]] = {group_id: [] for group_id in group_defs}
        statuses: dict[int, str] = {}
        time_used = 0.0
        memory_used = 0
        case_passed = 0

        for case in cases:
            case_number = int(case.get("case_number", 0))
            manifest_case = case_by_number.get(case_number)
            if manifest_case is None:
                continue
            status = str(case.get("status", SubmissionResult.IR))
            if status not in SubmissionResult.values:
                status = SubmissionResult.IR
            statuses[case_number] = status
            time_used = max(time_used, float(case.get("time_used", 0.0) or 0.0))
            memory_used = max(memory_used, int(case.get("memory_used", 0) or 0))
            if status == SubmissionResult.AC:
                case_passed += 1

            maximum = float(manifest_case.get("points", 0) or 0)
            reported = float(case.get("points", 0) or 0)
            reported_total = float(case.get("total_points", maximum) or maximum)
            if status == SubmissionResult.AC and reported <= 0:
                reported = reported_total or maximum
            ratio = min(max(reported / reported_total, 0.0), 1.0) if reported_total > 0 else (1.0 if status == SubmissionResult.AC else 0.0)
            group_id = str(manifest_case.get("group", "default"))
            case_scores.setdefault(group_id, []).append(round(maximum * ratio, 4))

        subtask_scores: dict[str, float] = {}
        for group_id, scores in case_scores.items():
            group = group_defs.get(group_id, {"id": group_id, "mode": "sum"})
            mode = str(group.get("mode", "sum"))
            group_score = min(scores) if mode == "min" else sum(scores)
            group_cap = float(group.get("points", 0) or 0)
            if group_cap > 0:
                group_score = min(group_score, group_cap)
            subtask_scores[group_id] = round(group_score, 4)

        total_possible = sum(float(group.get("points", 0) or 0) for group in groups)
        points = round(sum(subtask_scores.values()), 2)
        case_total = len(manifest_cases) or len(cases)

        result = ScoringService._aggregate_result(statuses, points, total_possible, case_total, case_passed)
        if not bool(manifest.get("partial_score", False)) and result not in {
            SubmissionResult.AC,
            SubmissionResult.CE,
            SubmissionResult.IE,
        }:
            points = 0.0
            subtask_scores = {group_id: 0.0 for group_id in subtask_scores}
            if result == SubmissionResult.PARTIAL:
                result = SubmissionResult.WA
        status = SubmissionStatus.ERROR if result in {SubmissionResult.CE, SubmissionResult.IE} else SubmissionStatus.COMPLETED

        return ScoreSummary(
            points=points,
            subtask_scores=subtask_scores,
            result=result,
            status=status,
            case_total=case_total,
            case_passed=case_passed,
            time_used=time_used,
            memory_used=memory_used,
        )

    @staticmethod
    def _aggregate_result(
        statuses: dict[int, str],
        points: float,
        total_possible: float,
        case_total: int,
        case_passed: int,
    ) -> str:
        values = set(statuses.values())
        if SubmissionResult.CE in values:
            return SubmissionResult.CE
        if SubmissionResult.IE in values:
            return SubmissionResult.IE
        for verdict in (
            SubmissionResult.TLE,
            SubmissionResult.MLE,
            SubmissionResult.RTE,
            SubmissionResult.OLE,
        ):
            if verdict in values:
                return verdict
        if case_total > 0 and case_passed == case_total and (total_possible <= 0 or points >= total_possible):
            return SubmissionResult.AC
        if points > 0:
            return SubmissionResult.PARTIAL
        return SubmissionResult.WA
