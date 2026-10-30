from __future__ import annotations

from datetime import timedelta
from functools import partial
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.judge.models import Judge, JudgeJob, JudgeJobStatus
from apps.judge.services.scoring_service import ScoringService
from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.models import Submission, SubmissionTestCase
from core.events import (
    SUBMISSION_CASE,
    SUBMISSION_FINISHED,
    SUBMISSION_STATUS,
    Event,
    publish_sync,
)
from core.exceptions import JudgeJobConflictError, PermissionDeniedError

LEASE_SECONDS = 60


class JudgeResultService:
    """Apply worker progress/final callbacks with server-side validation."""

    @staticmethod
    def _lock_job(job: JudgeJob) -> JudgeJob:
        return JudgeJob.objects.select_for_update().get(pk=job.pk)

    @staticmethod
    def _assert_owned(job: JudgeJob, judge: Judge) -> None:
        if job.claimed_by_id != judge.id:
            raise PermissionDeniedError("This job is claimed by another judge.")
        if job.lease_expires_at is None or job.lease_expires_at <= timezone.now():
            raise JudgeJobConflictError("The judge job lease has expired.")
        if job.status not in {JudgeJobStatus.CLAIMED, JudgeJobStatus.RUNNING}:
            raise JudgeJobConflictError("The judge job is not active.")

    @staticmethod
    def _extend_lease(job: JudgeJob) -> None:
        job.lease_expires_at = timezone.now() + timedelta(seconds=LEASE_SECONDS)

    @staticmethod
    def _manifest_case(job: JudgeJob, case_number: int) -> dict[str, Any]:
        manifest_cases = (job.package.manifest or {}).get("cases") or []
        index = case_number - 1
        if index < 0 or index >= len(manifest_cases):
            return {}
        return manifest_cases[index]

    @staticmethod
    def _publish(event_type: str, payload: dict[str, Any], submission_id: int) -> None:
        transaction.on_commit(
            partial(
                publish_sync,
                Event(type=event_type, payload=payload),
                group=f"submission_{submission_id}",
            )
        )

    @staticmethod
    @transaction.atomic
    def start(job: JudgeJob, judge: Judge) -> None:
        """Mark a claimed job as running."""

        locked = JudgeResultService._lock_job(job)
        if locked.status == JudgeJobStatus.RUNNING:
            return
        JudgeResultService._assert_owned(locked, judge)
        if locked.status != JudgeJobStatus.CLAIMED:
            raise JudgeJobConflictError("The judge job cannot be started.")
        locked.status = JudgeJobStatus.RUNNING
        locked.started_at = timezone.now()
        JudgeResultService._extend_lease(locked)
        locked.save(update_fields=["status", "started_at", "lease_expires_at", "updated_at"])
        Submission.objects.filter(pk=locked.submission_id).update(status=SubmissionStatus.JUDGING)
        JudgeResultService._publish(
            SUBMISSION_STATUS,
            {
                "submission_id": locked.submission_id,
                "status": SubmissionStatus.JUDGING,
                "current_testcase": 0,
            },
            locked.submission_id,
        )

    @staticmethod
    @transaction.atomic
    def record_cases(job: JudgeJob, judge: Judge, cases: list[dict[str, Any]]) -> None:
        """Upsert a batch of per-case results."""

        locked = JudgeResultService._lock_job(job)
        JudgeResultService._assert_owned(locked, judge)
        if locked.status == JudgeJobStatus.CLAIMED:
            locked.status = JudgeJobStatus.RUNNING
            locked.started_at = locked.started_at or timezone.now()

        submission = locked.submission
        max_case = submission.current_testcase
        for case in cases:
            case_number = int(case.get("case_number", 0))
            if case_number <= 0:
                continue
            status = str(case.get("status", SubmissionResult.IR))
            if status not in SubmissionResult.values:
                status = SubmissionResult.IR
            manifest_case = JudgeResultService._manifest_case(locked, case_number)
            SubmissionTestCase.objects.update_or_create(
                submission=submission,
                case_number=case_number,
                defaults={
                    "status": status,
                    "time_used": float(case.get("time_used", 0.0) or 0.0),
                    "memory_used": int(case.get("memory_used", 0) or 0),
                    "points": float(case.get("points", 0.0) or 0.0),
                    "total_points": float(case.get("total_points", 0.0) or 0.0),
                    "feedback": str(case.get("feedback", "")),
                    "output": str(case.get("output", "")),
                    "group": str(manifest_case.get("group", "default")),
                },
            )
            max_case = max(max_case, case_number)

        manifest_cases = (locked.package.manifest or {}).get("cases") or []
        case_total = len(manifest_cases) or submission.test_cases.count()
        case_passed = submission.test_cases.filter(status=SubmissionResult.AC).count()
        submission.status = SubmissionStatus.JUDGING
        submission.case_total = case_total
        submission.case_passed = case_passed
        submission.current_testcase = max_case
        submission.save(
            update_fields=[
                "status",
                "case_total",
                "case_passed",
                "current_testcase",
                "updated_at",
            ]
        )

        JudgeResultService._extend_lease(locked)
        locked.save(update_fields=["status", "started_at", "lease_expires_at", "updated_at"])
        JudgeResultService._publish(
            SUBMISSION_CASE,
            {
                "submission_id": submission.pk,
                "cases": cases,
                "case_total": case_total,
                "case_passed": case_passed,
                "current_testcase": max_case,
            },
            submission.pk,
        )

    @staticmethod
    @transaction.atomic
    def finish(job: JudgeJob, judge: Judge, payload: dict[str, Any]) -> Submission:
        """Finalize a job using server-computed scores."""

        locked = JudgeResultService._lock_job(job)
        submission = locked.submission
        if locked.status == JudgeJobStatus.SUCCEEDED:
            return submission
        JudgeResultService._assert_owned(locked, judge)
        if locked.status not in {JudgeJobStatus.CLAIMED, JudgeJobStatus.RUNNING}:
            raise JudgeJobConflictError("The judge job cannot be finished.")

        rows = list(SubmissionTestCase.objects.filter(submission=submission).order_by("case_number"))
        case_payloads = [
            {
                "case_number": row.case_number,
                "status": row.status,
                "time_used": row.time_used,
                "memory_used": row.memory_used,
                "points": row.points,
                "total_points": row.total_points,
                "feedback": row.feedback,
            }
            for row in rows
        ]
        summary = ScoringService.score(locked.package, case_payloads)

        submission.status = summary.status
        submission.result = summary.result
        submission.points = summary.points
        submission.time_used = summary.time_used
        submission.memory_used = summary.memory_used
        submission.case_total = summary.case_total
        submission.case_passed = summary.case_passed
        submission.current_testcase = max((row.case_number for row in rows), default=0)
        submission.subtask_scores = summary.subtask_scores
        submission.judged_at = timezone.now()
        submission.judged_on = judge
        submission.error_message = str(payload.get("error_message", ""))
        submission.save(
            update_fields=[
                "status",
                "result",
                "points",
                "time_used",
                "memory_used",
                "case_total",
                "case_passed",
                "current_testcase",
                "subtask_scores",
                "judged_at",
                "judged_on",
                "error_message",
                "updated_at",
            ]
        )

        locked.status = JudgeJobStatus.SUCCEEDED
        locked.finished_at = timezone.now()
        locked.lease_expires_at = None
        locked.last_error = ""
        locked.save(update_fields=["status", "finished_at", "lease_expires_at", "last_error", "updated_at"])
        JudgeResultService._publish(
            SUBMISSION_FINISHED,
            {
                "submission_id": submission.pk,
                "status": submission.status,
                "result": submission.result,
                "points": submission.points,
                "time_used": submission.time_used,
                "memory_used": submission.memory_used,
                "case_total": submission.case_total,
                "case_passed": submission.case_passed,
            },
            submission.pk,
        )
        return submission

    @staticmethod
    @transaction.atomic
    def fail(job: JudgeJob, judge: Judge, payload: dict[str, Any]) -> Submission:
        """Finalize a job as a compile/internal error."""

        locked = JudgeResultService._lock_job(job)
        submission = locked.submission
        if locked.status == JudgeJobStatus.FAILED:
            return submission
        JudgeResultService._assert_owned(locked, judge)
        if locked.status not in {JudgeJobStatus.CLAIMED, JudgeJobStatus.RUNNING}:
            raise JudgeJobConflictError("The judge job cannot be failed.")

        result = str(payload.get("result", SubmissionResult.IE))
        if result not in SubmissionResult.values:
            result = SubmissionResult.IE
        submission.status = SubmissionStatus.ERROR
        submission.result = result
        submission.points = 0.0
        submission.time_used = 0.0
        submission.memory_used = 0
        submission.case_total = 0
        submission.case_passed = 0
        submission.current_testcase = 0
        submission.subtask_scores = {}
        submission.error_message = str(payload.get("error_message", ""))
        submission.judged_at = timezone.now()
        submission.judged_on = judge
        submission.save(
            update_fields=[
                "status",
                "result",
                "points",
                "time_used",
                "memory_used",
                "case_total",
                "case_passed",
                "current_testcase",
                "subtask_scores",
                "error_message",
                "judged_at",
                "judged_on",
                "updated_at",
            ]
        )

        locked.status = JudgeJobStatus.FAILED
        locked.finished_at = timezone.now()
        locked.lease_expires_at = None
        locked.last_error = submission.error_message
        locked.save(update_fields=["status", "finished_at", "lease_expires_at", "last_error", "updated_at"])
        JudgeResultService._publish(
            SUBMISSION_FINISHED,
            {
                "submission_id": submission.pk,
                "status": submission.status,
                "result": submission.result,
                "error_message": submission.error_message,
            },
            submission.pk,
        )
        return submission
