from __future__ import annotations

from django.db import models

from apps.submissions.constants import SubmissionResult
from core.models import TimestampedModel


class SubmissionTestCase(TimestampedModel):
    """Per-test-case execution result for a submission."""

    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.CASCADE,
        related_name="test_cases",
    )
    case_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=8,
        choices=SubmissionResult.choices,
        default=SubmissionResult.IR,
    )
    time_used = models.FloatField(default=0.0)
    memory_used = models.PositiveIntegerField(default=0)
    points = models.FloatField(default=0.0)
    total_points = models.FloatField(default=0.0)
    group = models.CharField(max_length=32, blank=True, default="default")
    feedback = models.TextField(blank=True)
    output = models.TextField(blank=True)
    batch_number = models.PositiveIntegerField(null=True, blank=True)

    class Meta(TimestampedModel.Meta):
        db_table = "submissions_test_case"
        ordering = ["case_number"]
        verbose_name = "Submission Test Case"
        verbose_name_plural = "Submission Test Cases"
        unique_together = (("submission", "case_number"),)
        indexes = [
            models.Index(fields=["submission", "case_number"], name="subtc_sub_case_idx"),
            models.Index(fields=["submission", "status"], name="subtc_sub_status_idx"),
            models.Index(fields=["created_at"], name="subtc_created_idx"),
        ]

    def __str__(self) -> str:
        """Return a concise identifier for admin and logs.

        Returns:
            A string representation containing the submission id and case number.
        """
        return f"SubmissionTestCase(submission_id={self.submission_id}, case={self.case_number})"
