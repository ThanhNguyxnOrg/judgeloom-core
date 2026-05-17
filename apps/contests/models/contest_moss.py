from __future__ import annotations

from django.db import models

from core.models import TimestampedModel


class ContestMossStatus(models.TextChoices):
    """Processing status for MOSS plagiarism checks."""

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ContestMoss(TimestampedModel):
    """Stores MOSS run requests/results for contest submissions."""

    contest = models.ForeignKey("contests.Contest", on_delete=models.CASCADE, related_name="moss_runs")
    problem = models.ForeignKey(
        "problems.Problem", on_delete=models.SET_NULL, null=True, blank=True, related_name="moss_runs"
    )
    language = models.ForeignKey(
        "judge.Language", on_delete=models.SET_NULL, null=True, blank=True, related_name="moss_runs"
    )
    submission_limit = models.PositiveIntegerField(null=True, blank=True)
    result_url = models.URLField(blank=True)
    status = models.CharField(max_length=16, choices=ContestMossStatus.choices, default=ContestMossStatus.PENDING)

    class Meta:
        db_table = "contests_moss"
        verbose_name = "Contest MOSS Run"
        verbose_name_plural = "Contest MOSS Runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contest", "status"], name="contest_moss_status_idx"),
            models.Index(fields=["created_at"], name="contest_moss_created_idx"),
        ]

    def __str__(self) -> str:
        """Return human-readable MOSS run descriptor."""

        return f"MOSS<{self.contest.key}:{self.status}>"
