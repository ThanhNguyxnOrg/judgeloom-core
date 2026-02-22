from __future__ import annotations

from django.db import models

from core.models import TimestampedModel
from core.validators import validate_memory_limit, validate_time_limit

class LanguageLimit(TimestampedModel):
    """Per-language execution constraints for a specific problem."""

    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="language_limits")
    language = models.ForeignKey("judge.Language", on_delete=models.CASCADE, related_name="problem_limits")
    time_limit = models.FloatField(validators=[validate_time_limit])
    memory_limit = models.PositiveIntegerField(validators=[validate_memory_limit])

    class Meta:
        db_table = "problems_language_limit"
        ordering = ("problem__code", "language__name")
        verbose_name = "Problem language limit"
        verbose_name_plural = "Problem language limits"
        unique_together = (("problem", "language"),)
        indexes = [
            models.Index(fields=["problem", "language"], name="prob_lang_limit_idx"),
        ]

    def __str__(self) -> str:
        """Return a concise representation for the admin site."""

        return f"{self.problem.code} / {self.language}"
