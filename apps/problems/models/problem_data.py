from __future__ import annotations

from django.db import models

from apps.problems.constants import CheckerType
from core.models import TimestampedModel

class ProblemTestData(TimestampedModel):
    """Stores testcase artifacts and judging configuration for a problem."""

    problem = models.OneToOneField(
        "problems.Problem",
        on_delete=models.CASCADE,
        related_name="test_data",
    )
    zipfile = models.FileField(upload_to="problem_test_data/archives/", null=True, blank=True)
    generator = models.FileField(upload_to="problem_test_data/generators/", null=True, blank=True)
    output_prefix = models.IntegerField(default=0)
    output_limit = models.IntegerField(default=65536)
    checker = models.CharField(max_length=32, choices=CheckerType.choices, default=CheckerType.STANDARD)
    checker_source = models.FileField(upload_to="problem_test_data/checkers/", null=True, blank=True)
    custom_checker_language = models.ForeignKey(
        "judge.Language",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="custom_checker_test_data",
    )
    interactive_judge = models.FileField(upload_to="problem_test_data/interactive/", null=True, blank=True)

    class Meta:
        db_table = "problems_test_data"
        ordering = ("problem__code",)
        verbose_name = "Problem test data"
        verbose_name_plural = "Problem test data"
        indexes = [
            models.Index(fields=["checker"], name="prob_tdata_checker_idx"),
            models.Index(fields=["output_prefix"], name="prob_tdata_prefix_idx"),
        ]

    def __str__(self) -> str:
        """Return a readable representation for administration."""

        return f"Test data for {self.problem.code}"
