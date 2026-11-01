from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.judge.models import Judge, JudgeJobStatus, ShadowJob
from apps.submissions.constants import SubmissionMode, SubmissionResult
from core.exceptions import JudgeJobConflictError, PermissionDeniedError

LEASE_SECONDS = 60


class ShadowJobService:
    """Queue and apply non-scoring replay jobs."""

    @staticmethod
    @transaction.atomic
    def create_for_submission(submission: Any, target_judge: Judge | None = None) -> ShadowJob:
        job = getattr(submission, "judge_job", None)
        package = job.package if job is not None else submission.problem.packages.filter(is_active=True).first()
        if package is None and submission.mode != SubmissionMode.RUN:
            raise ValueError("No active test data package is available for this problem.")

        config = dict(job.config) if job is not None else {
            "time_limit": submission.problem.time_limit,
            "memory_limit": submission.problem.memory_limit,
            "mode": submission.mode,
            "custom_input": submission.custom_input,
            "expected_output": submission.custom_expected_output,
        }
        config.setdefault("mode", submission.mode)
        config.setdefault("custom_input", submission.custom_input)

        return ShadowJob.objects.create(
            submission=submission,
            package=package,
            language=submission.language,
            target_judge=target_judge,
            config=config,
        )

    @staticmethod
    @transaction.atomic
    def claim_job(judge: Judge, languages: list[str]) -> ShadowJob | None:
        now = timezone.now()
        ShadowJob.objects.select_for_update(skip_locked=True).filter(
            status__in=[JudgeJobStatus.CLAIMED, JudgeJobStatus.RUNNING],
            lease_expires_at__lt=now,
        ).update(
            status=JudgeJobStatus.QUEUED,
            claimed_by=None,
            claimed_at=None,
            started_at=None,
            lease_expires_at=None,
            error_message="Shadow lease expired; job requeued.",
        )

        job = (
            ShadowJob.objects.select_for_update(skip_locked=True)
            .filter(status=JudgeJobStatus.QUEUED, language__key__in=languages)
            .filter(models_target_judge(judge))
            .order_by("-priority", "created_at")
            .first()
        )
        if job is None:
            return None

        job.status = JudgeJobStatus.CLAIMED
        job.claimed_by = judge
        job.claimed_at = now
        job.attempts += 1
        job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        job.save(
            update_fields=[
                "status",
                "claimed_by",
                "claimed_at",
                "attempts",
                "lease_expires_at",
                "updated_at",
            ]
        )
        return job

    @staticmethod
    def claim_payload(job: ShadowJob) -> dict[str, Any]:
        manifest = (job.package.manifest if job.package is not None else {}) or {}
        config = job.config or {}
        source = getattr(job.submission, "source", None)
        package_payload = None
        if job.package is not None:
            package_payload = {
                "problem_id": job.package.problem_id,
                "sha256": job.package.sha256,
                "url": f"/api/v1/judge/packages/{job.package.problem_id}?sha256={job.package.sha256}",
            }

        return {
            "job_id": job.pk,
            "submission_id": job.submission_id,
            "language": job.language.key,
            "source": source.source_code if source is not None else "",
            "limits": {
                "time": config.get("time_limit", manifest.get("time_limit")),
                "memory": config.get("memory_limit", manifest.get("memory_limit")),
            },
            "short_circuit": bool(config.get("short_circuit", False)),
            "partial_score": bool(config.get("partial_score", False)),
            "contest_points": None,
            "mode": config.get("mode", SubmissionMode.SUBMIT),
            "custom_input": config.get("custom_input", ""),
            "expected_output": config.get("expected_output", ""),
            "package": package_payload,
            "checker": manifest.get("checker") or {"type": "exact"},
            "cases": manifest.get("cases") or [],
            "groups": manifest.get("groups") or [],
            "lease_seconds": LEASE_SECONDS,
        }

    @staticmethod
    def _lock(job: ShadowJob) -> ShadowJob:
        return ShadowJob.objects.select_for_update().get(pk=job.pk)

    @staticmethod
    def _assert_owned(job: ShadowJob, judge: Judge) -> None:
        now = timezone.now()
        if job.claimed_by_id != judge.id:
            raise PermissionDeniedError("This shadow job is claimed by another judge.")
        if job.lease_expires_at is None or job.lease_expires_at <= now:
            raise JudgeJobConflictError("The shadow job lease has expired.")
        if job.status not in {JudgeJobStatus.CLAIMED, JudgeJobStatus.RUNNING}:
            raise JudgeJobConflictError("The shadow job is not active.")

    @staticmethod
    @transaction.atomic
    def start(job: ShadowJob, judge: Judge) -> None:
        locked = ShadowJobService._lock(job)
        ShadowJobService._assert_owned(locked, judge)
        locked.status = JudgeJobStatus.RUNNING
        locked.started_at = locked.started_at or timezone.now()
        locked.lease_expires_at = timezone.now() + timedelta(seconds=LEASE_SECONDS)
        locked.save(update_fields=["status", "started_at", "lease_expires_at", "updated_at"])

    @staticmethod
    @transaction.atomic
    def record_cases(job: ShadowJob, judge: Judge, cases: list[dict[str, Any]]) -> None:
        locked = ShadowJobService._lock(job)
        ShadowJobService._assert_owned(locked, judge)
        locked.status = JudgeJobStatus.RUNNING
        locked.started_at = locked.started_at or timezone.now()
        locked.case_results = cases
        locked.case_total = len(cases)
        locked.case_passed = sum(1 for case in cases if case.get("status") == SubmissionResult.AC)
        locked.lease_expires_at = timezone.now() + timedelta(seconds=LEASE_SECONDS)
        locked.save(
            update_fields=[
                "status",
                "started_at",
                "case_results",
                "case_total",
                "case_passed",
                "lease_expires_at",
                "updated_at",
            ]
        )

    @staticmethod
    @transaction.atomic
    def finish(job: ShadowJob, judge: Judge, payload: dict[str, Any]) -> ShadowJob:
        locked = ShadowJobService._lock(job)
        ShadowJobService._assert_owned(locked, judge)
        cases = locked.case_results or []
        result = SubmissionResult.AC
        for case in cases:
            status = str(case.get("status", SubmissionResult.IE))
            if status != SubmissionResult.AC:
                result = status
                break
        if not cases:
            result = str(payload.get("result") or SubmissionResult.IE)

        locked.status = JudgeJobStatus.SUCCEEDED
        locked.result = result
        locked.total_points = sum(float(case.get("points", 0.0) or 0.0) for case in cases)
        locked.case_total = len(cases)
        locked.case_passed = sum(1 for case in cases if case.get("status") == SubmissionResult.AC)
        locked.error_message = str(payload.get("error_message", ""))
        locked.finished_at = timezone.now()
        locked.lease_expires_at = None
        locked.save(
            update_fields=[
                "status",
                "result",
                "total_points",
                "case_total",
                "case_passed",
                "error_message",
                "finished_at",
                "lease_expires_at",
                "updated_at",
            ]
        )
        return locked

    @staticmethod
    @transaction.atomic
    def fail(job: ShadowJob, judge: Judge, payload: dict[str, Any]) -> ShadowJob:
        locked = ShadowJobService._lock(job)
        ShadowJobService._assert_owned(locked, judge)
        result = str(payload.get("result", SubmissionResult.IE))
        if result not in {SubmissionResult.CE, SubmissionResult.IE}:
            result = SubmissionResult.IE
        locked.status = JudgeJobStatus.FAILED
        locked.result = result
        locked.error_message = str(payload.get("error_message", ""))
        locked.finished_at = timezone.now()
        locked.lease_expires_at = None
        locked.save(
            update_fields=[
                "status",
                "result",
                "error_message",
                "finished_at",
                "lease_expires_at",
                "updated_at",
            ]
        )
        return locked


def models_target_judge(judge: Judge):
    from django.db.models import Q

    return Q(target_judge__isnull=True) | Q(target_judge=judge)
