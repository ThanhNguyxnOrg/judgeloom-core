from __future__ import annotations

from django.db import models

from core.models import TimestampedModel


class JudgeJobStatus(models.TextChoices):
    """Lifecycle states for one judge job."""

    QUEUED = "queued", "Queued"
    CLAIMED = "claimed", "Claimed"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    EXPIRED = "expired", "Expired"
    CANCELLED = "cancelled", "Cancelled"


class JudgeJob(TimestampedModel):
    """A leased unit of work for one submission."""

    submission = models.OneToOneField(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="judge_job",
    )
    package = models.ForeignKey(
        "problems.ProblemPackage",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="judge_jobs",
    )
    language = models.ForeignKey(
        "judge.Language",
        on_delete=models.PROTECT,
        related_name="judge_jobs",
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
        related_name="claimed_jobs",
    )
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    config = models.JSONField(default=dict)
    last_error = models.TextField(blank=True, default="")
    claimed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimestampedModel.Meta):
        db_table = "judge_job"
        verbose_name = "Judge Job"
        verbose_name_plural = "Judge Jobs"
        ordering = ["-priority", "created_at"]
        indexes = [
            models.Index(fields=["status", "priority", "created_at"], name="judge_job_queue_idx"),
            models.Index(fields=["lease_expires_at"], name="judge_job_lease_idx"),
            models.Index(fields=["claimed_by", "status"], name="judge_job_claim_idx"),
        ]

    def __str__(self) -> str:
        return f"JudgeJob(submission={self.submission_id}, status={self.status})"
