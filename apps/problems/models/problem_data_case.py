from __future__ import annotations

from django.db import models

from core.models import TimestampedModel

class ProblemTestCase(TimestampedModel):
    """Represents an individual testcase inside a problem's test data."""

    problem_data = models.ForeignKey(
        "problems.ProblemTestData",
        on_delete=models.CASCADE,
        related_name="test_cases",
    )
    order = models.PositiveIntegerField()
    input_file = models.CharField(max_length=255)
    output_file = models.CharField(max_length=255)
    points = models.FloatField(default=0.0)
    is_pretest = models.BooleanField(default=False)
    batch_number = models.PositiveIntegerField(null=True, blank=True)
    batch_points = models.FloatField(default=0.0)

    class Meta:
        db_table = "problems_test_case"
        ordering = ("order",)
        verbose_name = "Problem test case"
        verbose_name_plural = "Problem test cases"
        unique_together = (("problem_data", "order"),)
        indexes = [
            models.Index(fields=["problem_data", "order"], name="prob_tcase_order_idx"),
            models.Index(fields=["is_pretest"], name="prob_tcase_pretest_idx"),
        ]

    def __str__(self) -> str:
        """Return a compact testcase descriptor."""

        return f"Case #{self.order} ({self.problem_data.problem.code})"
