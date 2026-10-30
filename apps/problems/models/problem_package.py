from __future__ import annotations

from django.db import models

from core.models import TimestampedModel


class ProblemPackage(TimestampedModel):
    """Immutable, content-addressed set of test data for a problem."""

    problem = models.ForeignKey(
        "problems.Problem",
        on_delete=models.CASCADE,
        related_name="packages",
    )
    version = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    manifest = models.JSONField(default=dict)
    archive = models.FileField(upload_to="problem_packages/")
    size_bytes = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=False)

    class Meta(TimestampedModel.Meta):
        db_table = "problems_package"
        verbose_name = "Problem Package"
        verbose_name_plural = "Problem Packages"
        ordering = ("problem_id", "-version")
        unique_together = (("problem", "sha256"),)
        indexes = [
            models.Index(fields=["problem", "is_active"], name="prob_pkg_active_idx"),
            models.Index(fields=["sha256"], name="prob_pkg_sha_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.problem.code} package v{self.version} ({self.sha256[:12]})"
