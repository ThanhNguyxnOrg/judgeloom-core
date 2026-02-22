from __future__ import annotations

from django.db import models

from apps.problems.constants import SolutionVerdict
from core.models import TimestampedModel

class Solution(TimestampedModel):
    """Stores user-authored writeups or official solutions for problems."""

    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="solutions")
    author = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="solutions")
    content = models.TextField()
    is_public = models.BooleanField(default=False)
    verdict = models.CharField(max_length=32, choices=SolutionVerdict.choices, null=True, blank=True)

    class Meta:
        db_table = "problems_solution"
        ordering = ("-created_at",)
        verbose_name = "Problem solution"
        verbose_name_plural = "Problem solutions"
        indexes = [
            models.Index(fields=["problem", "created_at"], name="prob_sol_created_idx"),
            models.Index(fields=["author"], name="prob_sol_author_idx"),
            models.Index(fields=["verdict"], name="prob_sol_verdict_idx"),
        ]

    def __str__(self) -> str:
        """Return a compact label for admin interfaces."""

        return f"Solution #{self.pk} for {self.problem.code}"
