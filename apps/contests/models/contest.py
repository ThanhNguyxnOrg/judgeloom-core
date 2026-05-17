from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.contests.constants import ContestFormat, ContestVisibility
from core.models import SluggedModel


class Contest(SluggedModel):
    """Represents a contest and all of its scheduling/configuration metadata."""

    name = models.CharField(max_length=255)
    key = models.CharField(max_length=32, unique=True)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    time_limit = models.DurationField(null=True, blank=True)
    visibility = models.CharField(
        max_length=32,
        choices=ContestVisibility.choices,
        default=ContestVisibility.PRIVATE,
    )

    is_rated = models.BooleanField(default=False)
    rate_all = models.BooleanField(default=False)
    rate_exclude = models.ManyToManyField("accounts.User", blank=True, related_name="rating_excluded_contests")
    rating_floor = models.IntegerField(null=True, blank=True)
    rating_ceiling = models.IntegerField(null=True, blank=True)

    organizers = models.ManyToManyField("accounts.User", related_name="organized_contests")
    curators = models.ManyToManyField("accounts.User", related_name="curated_contests", blank=True)
    testers = models.ManyToManyField("accounts.User", related_name="tested_contests", blank=True)
    organizations = models.ManyToManyField("organizations.Organization", blank=True, related_name="contests")
    is_organization_private = models.BooleanField(default=False)

    problems = models.ManyToManyField("problems.Problem", through="ContestProblem", related_name="contests")

    format_name = models.CharField(
        max_length=32,
        choices=ContestFormat.choices,
        default=ContestFormat.DEFAULT,
    )
    format_config = models.JSONField(default=dict)
    scoreboard_frozen_after = models.DurationField(null=True, blank=True)

    points_precision = models.PositiveIntegerField(default=2)
    run_pretests_only = models.BooleanField(default=False)

    access_code = models.CharField(max_length=128, null=True, blank=True)
    banned_users = models.ManyToManyField("accounts.User", blank=True, related_name="banned_from_contests")

    is_visible = models.BooleanField(default=True)
    show_short_display = models.BooleanField(default=False)

    class Meta:
        db_table = "contests_contest"
        verbose_name = "Contest"
        verbose_name_plural = "Contests"
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["key"], name="contest_key_idx"),
            models.Index(fields=["start_time"], name="contest_start_idx"),
            models.Index(fields=["end_time"], name="contest_end_idx"),
        ]

    @property
    def is_active(self) -> bool:
        """Return whether the contest is currently active."""

        now = timezone.now()
        return self.start_time <= now < self.end_time

    @property
    def is_finished(self) -> bool:
        """Return whether the contest has ended."""

        return timezone.now() >= self.end_time

    @property
    def is_upcoming(self) -> bool:
        """Return whether the contest has not yet started."""

        return timezone.now() < self.start_time

    @property
    def duration(self) -> timedelta:
        """Return total scheduled duration of the contest."""

        return self.end_time - self.start_time

    @property
    def time_remaining(self) -> timedelta:
        """Return remaining time when active, or zero otherwise."""

        now = timezone.now()
        if not self.is_active:
            return timedelta(0)
        return max(self.end_time - now, timedelta(0))

    @property
    def is_frozen(self) -> bool:
        """Return whether scoreboard freeze window is currently active."""

        if not self.scoreboard_frozen_after:
            return False
        now = timezone.now()
        freeze_time = self.start_time + self.scoreboard_frozen_after
        return freeze_time <= now < self.end_time

    def get_slug_source(self) -> str:
        """Return slug source used by SluggedModel.

        Returns:
            Contest short key.
        """

        return self.key

    def __str__(self) -> str:
        """Return human-readable contest name."""

        return f"{self.key} - {self.name}"
