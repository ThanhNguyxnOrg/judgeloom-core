from __future__ import annotations

from datetime import timedelta
from functools import partial
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.judge.models import Judge, JudgeJob, JudgeJobStatus
from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.models import Submission, SubmissionTestCase
from core.events import SUBMISSION_FINISHED, SUBMISSION_STATUS, Event, publish_sync

LEASE_SECONDS = 60


class JudgeGatewayService:
    """Claim and lease orchestration for judge workers."""

    @staticmethod
    @transaction.atomic
    def expire_stale_jobs() -> int:
        """Requeue expired jobs or fail them after the attempt limit.

        Returns:
            Number of jobs whose state changed.
        """

        now = timezone.now()
        stale_jobs = JudgeJob.objects.select_for_update(skip_locked=True).filter(
            status__in=[JudgeJobStatus.CLAIMED, JudgeJobStatus.RUNNING],
            lease_expires_at__lt=now,
        )

        changed = 0
        for job in stale_jobs:
            SubmissionTestCase.objects.filter(submission_id=job.submission_id).delete()
            if job.attempts >= job.max_attempts:
                job.status = JudgeJobStatus.FAILED
                job.finished_at = now
                job.lease_expires_at = None
                job.last_error = "Lease expired after maximum attempts."
                job.save(update_fields=["status", "finished_at", "lease_expires_at", "last_error", "updated_at"])
                Submission.objects.filter(pk=job.submission_id).update(
                    status=SubmissionStatus.ERROR,
                    result=SubmissionResult.IE,
                    points=0.0,
                    time_used=0.0,
                    memory_used=0,
                    case_total=0,
                    case_passed=0,
                    current_testcase=0,
                    subtask_scores={},
                    error_message="Judge lease expired after maximum attempts.",
                    judged_at=now,
                    judged_on=None,
                )
                transaction.on_commit(
                    partial(
                        publish_sync,
                        Event(
                            type=SUBMISSION_FINISHED,
                            payload={
                                "submission_id": job.submission_id,
                                "status": SubmissionStatus.ERROR,
                                "result": SubmissionResult.IE,
                                "points": 0.0,
                                "error_message": "Judge lease expired after maximum attempts.",
                            },
                        ),
                        group=f"submission_{job.submission_id}",
                    )
                )
            else:
                job.status = JudgeJobStatus.QUEUED
                job.claimed_by = None
                job.claimed_at = None
                job.started_at = None
                job.finished_at = None
                job.lease_expires_at = None
                job.last_error = "Lease expired; job requeued."
                job.save(
                    update_fields=[
                        "status",
                        "claimed_by",
                        "claimed_at",
                        "started_at",
                        "finished_at",
                        "lease_expires_at",
                        "last_error",
                        "updated_at",
                    ]
                )
                Submission.objects.filter(pk=job.submission_id).update(
                    status=SubmissionStatus.QUEUED,
                    result=None,
                    points=0.0,
                    time_used=0.0,
                    memory_used=0,
                    case_total=0,
                    case_passed=0,
                    current_testcase=0,
                    subtask_scores={},
                    error_message="",
                    judged_at=None,
                    judged_on=None,
                )
                transaction.on_commit(
                    partial(
                        publish_sync,
                        Event(
                            type=SUBMISSION_STATUS,
                            payload={
                                "submission_id": job.submission_id,
                                "status": SubmissionStatus.QUEUED,
                                "current_testcase": 0,
                            },
                        ),
                        group=f"submission_{job.submission_id}",
                    )
                )
            changed += 1
        return changed

    @staticmethod
    def claim_job(judge: Judge, languages: list[str], max_jobs: int = 1) -> JudgeJob | None:
        """Claim one queued job for a judge.

        Args:
            judge: Authenticated judge worker.
            languages: Language keys the worker can execute.
            max_jobs: Reserved for future batch claiming; v1 claims one.

        Returns:
            Claimed job, or None when no eligible job exists.
        """

        _ = max_jobs
        JudgeGatewayService.expire_stale_jobs()
        now = timezone.now()

        with transaction.atomic():
            job = (
                JudgeJob.objects.select_for_update(skip_locked=True, of=("self",))
                .filter(status=JudgeJobStatus.QUEUED, language__key__in=languages)
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
    def claim_payload(job: JudgeJob) -> dict[str, Any]:
        """Build the worker-facing payload for a claimed job.

        Args:
            job: Claimed job.

        Returns:
            JSON-serializable claim payload.
        """

        manifest = job.package.manifest or {}
        config = job.config or {}
        source = getattr(job.submission, "source", None)
        source_code = source.source_code if source is not None else ""
        cases = manifest.get("cases") or []
        groups = manifest.get("groups") or []

        return {
            "job_id": job.pk,
            "submission_id": job.submission_id,
            "language": job.language.key,
            "source": source_code,
            "limits": {
                "time": config.get("time_limit", manifest.get("time_limit")),
                "memory": config.get("memory_limit", manifest.get("memory_limit")),
            },
            "short_circuit": bool(config.get("short_circuit", False)),
            "partial_score": bool(config.get("partial_score", False)),
            "contest_points": config.get("contest_points"),
            "mode": config.get("mode", "submit"),
            "custom_input": config.get("custom_input", ""),
            "package": {
                "problem_id": job.package.problem_id,
                "sha256": job.package.sha256,
                "url": f"/api/v1/judge/packages/{job.package.problem_id}?sha256={job.package.sha256}",
            },
            "checker": manifest.get("checker") or {"type": "exact"},
            "cases": cases,
            "groups": groups,
            "lease_seconds": LEASE_SECONDS,
        }
