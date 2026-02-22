from __future__ import annotations

from django.db import models

class ProblemDifficulty(models.TextChoices):
    """Difficulty levels for competitive programming problems."""

    TRIVIAL = "10", "Trivial"
    EASY = "20", "Easy"
    MEDIUM = "30", "Medium"
    HARD = "40", "Hard"
    INSANE = "50", "Insane"

class ProblemVisibility(models.TextChoices):
    """Visibility options for problems."""

    PRIVATE = "private", "Private"
    UNLISTED = "unlisted", "Unlisted"
    PUBLIC = "public", "Public"
    CONTEST_ONLY = "contest_only", "Contest Only"

class SolutionVerdict(models.TextChoices):
    """Editorial solution verdict classifications."""

    CORRECT = "correct", "Correct"
    WRONG = "wrong", "Wrong"
    PARTIAL = "partial", "Partial"
    PRESENTATION_ERROR = "presentation_error", "Presentation Error"

class ProblemType(models.TextChoices):
    """Problem interaction styles supported by the judge."""

    STANDARD = "standard", "Standard"
    INTERACTIVE = "interactive", "Interactive"
    COMMUNICATION = "communication", "Communication"
    OUTPUT_ONLY = "output_only", "Output Only"
    MULTI_STEP = "multi_step", "Multi Step"

class CheckerType(models.TextChoices):
    """Built-in checker strategies for test data validation."""

    STANDARD = "standard", "Standard"
    FLOAT = "float", "Float"
    SPECIAL_JUDGE = "special_judge", "Special Judge"
    IDENTICAL = "identical", "Identical"
