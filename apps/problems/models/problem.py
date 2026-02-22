from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from apps.problems.constants import ProblemDifficulty, ProblemType, ProblemVisibility
from core.models import SluggedModel
from core.validators import validate_memory_limit, validate_time_limit

class Problem(SluggedModel):
    """Core problem entity used by the JudgeLoom platform."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    authors = models.ManyToManyField("accounts.User", related_name="authored_problems")
    curators = models.ManyToManyField("accounts.User", related_name="curated_problems", blank=True)
    testers = models.ManyToManyField("accounts.User", related_name="tested_problems", blank=True)
    description = models.TextField()
    time_limit = models.FloatField(
        default=getattr(settings, "DEFAULT_TIME_LIMIT", 2.0),
        validators=[validate_time_limit],
    )
    memory_limit = models.PositiveIntegerField(
        default=getattr(settings, "DEFAULT_MEMORY_LIMIT", 262144),
        validators=[validate_memory_limit],
    )
    difficulty = models.CharField(max_length=8, choices=ProblemDifficulty.choices, null=True, blank=True)
    points = models.FloatField(default=0.0)
    partial_score = models.BooleanField(default=False)
    short_circuit = models.BooleanField(default=False)
    languages_allowed = models.ManyToManyField("judge.Language", blank=True, related_name="problems")
    source = models.CharField(max_length=255, blank=True)
    visibility = models.CharField(
        max_length=16,
        choices=ProblemVisibility.choices,
        default=ProblemVisibility.PRIVATE,
    )
    is_manually_managed = models.BooleanField(default=False)
    is_organization_private = models.BooleanField(default=False)
    organizations = models.ManyToManyField("organizations.Organization", blank=True, related_name="problems")
    license = models.ForeignKey(
        "problems.License",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="problems",
    )
    og_image = models.CharField(max_length=512, blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        db_table = "problems_problem"
        ordering = ("code",)
        verbose_name = "Problem"
        verbose_name_plural = "Problems"
        indexes = [
            models.Index(fields=["code"], name="prob_code_idx"),
            models.Index(fields=["points"], name="prob_points_idx"),
            models.Index(fields=["visibility"], name="prob_visibility_idx"),
        ]

    def __str__(self) -> str:
        """Return readable problem representation."""

        return f"{self.code} - {self.name}"

    def get_slug_source(self) -> str:
        """Return value used to generate slug for the problem."""

        return self.code

    @property
    def is_public(self) -> bool:
        """Return whether this problem is publicly visible."""

        return self.visibility == ProblemVisibility.PUBLIC

    @property
    def types(self) -> list[str]:
        """Return inferred problem types based on configuration and test data."""

        problem_types: list[str] = [ProblemType.STANDARD]
        if self.partial_score:
            problem_types.append(ProblemType.MULTI_STEP)

        test_data = getattr(self, "test_data", None)
        if test_data is not None:
            if test_data.interactive_judge:
                problem_types.append(ProblemType.INTERACTIVE)
            if test_data.output_prefix > 0:
                problem_types.append(ProblemType.OUTPUT_ONLY)
            if test_data.checker == "special_judge":
                problem_types.append(ProblemType.COMMUNICATION)

        return sorted(set(problem_types))

    def is_accessible_by(self, user: Any) -> bool:
        """Check whether a user can access this problem instance.

        Args:
            user: Django user-like object.

        Returns:
            bool: True if the user can view the problem.
        """

        if self.is_public or self.visibility == ProblemVisibility.UNLISTED:
            return True

        if not getattr(user, "is_authenticated", False):
            return False

        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True

        user_id = getattr(user, "pk", None)
        if user_id is None:
            return False

        return (
            self.authors.filter(pk=user_id).exists()
            or self.curators.filter(pk=user_id).exists()
            or self.testers.filter(pk=user_id).exists()
        )
