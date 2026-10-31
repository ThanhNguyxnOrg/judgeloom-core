from __future__ import annotations

from django.db import models

from apps.submissions.constants import RESULT_CSS_CLASS, SubmissionResult, SubmissionStatus
from core.models import TimestampedModel


class Submission(TimestampedModel):
    """Represents a single code submission sent for judging."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="submissions")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="submissions")
    language = models.ForeignKey("judge.Language", on_delete=models.PROTECT, related_name="submissions")
    time_used = models.FloatField(default=0.0)
    memory_used = models.PositiveIntegerField(default=0)
    points = models.FloatField(default=0.0)
    result = models.CharField(max_length=8, choices=SubmissionResult.choices, null=True, blank=True)
    status = models.CharField(max_length=8, choices=SubmissionStatus.choices, default=SubmissionStatus.QUEUED)
    subtask_scores = models.JSONField(default=dict, blank=True)
    case_total = models.PositiveIntegerField(default=0)
    case_passed = models.PositiveIntegerField(default=0)
    current_testcase = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    contest_participation = models.ForeignKey(
        "contests.ContestParticipation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    is_public = models.BooleanField(default=False)
    share_token = models.UUIDField(null=True, blank=True, unique=True)
    is_pretested = models.BooleanField(default=False)
    judged_on = models.ForeignKey(
        "judge.Judge",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="judged_submissions",
    )
    judged_at = models.DateTimeField(null=True, blank=True)
    locked_after = models.DateTimeField(null=True, blank=True)

    @property
    def is_graded(self) -> bool:
        """Check whether the submission has finished grading.

        Returns:
            True when the submission reached a terminal state.
        """
        return self.status in {SubmissionStatus.COMPLETED, SubmissionStatus.ERROR}

    @property
    def result_class(self) -> str:
        """Get presentation CSS class for the current verdict.

        Returns:
            A short CSS class token.
        """
        if self.result is None:
            return "secondary"
        return RESULT_CSS_CLASS.get(self.result, "secondary")

    @property
    def memory_display(self) -> str:
        """Format memory usage for UI display.

        Returns:
            Formatted memory value in KB or MB.
        """
        if self.memory_used >= 1024:
            return f"{self.memory_used / 1024:.2f} MB"
        return f"{self.memory_used} KB"

    @property
    def time_display(self) -> str:
        """Format execution time for UI display.

        Returns:
            Formatted time in milliseconds or seconds.
        """
        if self.time_used < 1.0:
            return f"{self.time_used * 1000:.0f} ms"
        return f"{self.time_used:.3f} s"

    @property
    def score_percentage(self) -> float:
        """Compute score percentage using available totals.

        Returns:
            Percentage score in range 0-100.
        """
        if self.result == SubmissionResult.AC:
            return 100.0
        max_points = float(getattr(self.problem, "points", 0.0) or 0.0)
        if max_points > 0.0:
            return round((self.points / max_points) * 100.0, 2)
        if self.case_total > 0:
            return round((self.case_passed / self.case_total) * 100.0, 2)
        return 0.0

    class Meta(TimestampedModel.Meta):
        db_table = "submissions_submission"
        ordering = ["-created_at"]
        verbose_name = "Submission"
        verbose_name_plural = "Submissions"
        indexes = [
            models.Index(fields=["user", "problem"], name="sub_user_problem_idx"),
            models.Index(fields=["problem", "result"], name="sub_problem_result_idx"),
            models.Index(fields=["status"], name="sub_status_idx"),
            models.Index(fields=["created_at"], name="sub_created_idx"),
        ]

    def __str__(self) -> str:
        """Return a concise identifier for admin and logs.

        Returns:
            A string representation containing id and status.
        """
        return f"Submission(id={self.id}, status={self.status})"
