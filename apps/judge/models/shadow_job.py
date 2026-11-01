from __future__ import annotations

from django.db import models

from apps.judge.models.judge_job import JudgeJobStatus
from core.models import TimestampedModel


class ShadowJob(TimestampedModel):
    """A non-scoring replay of a submission, optionally pinned to one judge."""

    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="shadow_jobs",
    )
    package = models.ForeignKey(
        "problems.ProblemPackage",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="shadow_jobs",
    )
    language = models.ForeignKey(
        "judge.Language",
        on_delete=models.PROTECT,
        related_name="shadow_jobs",
    )
    target_judge = models.ForeignKey(
        "judge.Judge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shadow_jobs",
    )
    status = models.CharField(
        max_length=16,
        choices=JudgeJobStatus.choices,
        default=JudgeJobStatus.QUEUED,
    )
    priority = models.IntegerField(default=0)
    claimed_by = models.ForeignKey(
        "judge.Judge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claimed_shadow_jobs",
    )
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    config = models.JSONField(default=dict)
    case_results = models.JSONField(default=list, blank=True)
    result = models.CharField(max_length=8, blank=True, default="")
    total_points = models.FloatField(default=0.0)
    case_total = models.PositiveIntegerField(default=0)
    case_passed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    claimed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimestampedModel.Meta):
        db_table = "judge_shadow_job"
        verbose_name = "Shadow Judge Job"
        verbose_name_plural = "Shadow Judge Jobs"
        ordering = ["-priority", "created_at"]
        indexes = [
            models.Index(fields=["status", "priority", "created_at"], name="shadow_job_queue_idx"),
            models.Index(fields=["target_judge", "status"], name="shadow_job_target_idx"),
            models.Index(fields=["lease_expires_at"], name="shadow_job_lease_idx"),
        ]

    def __str__(self) -> str:
        return f"ShadowJob(submission={self.submission_id}, status={self.status})"
