from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django.utils import timezone

from core.models import TimestampedModel

if TYPE_CHECKING:
    from datetime import timedelta


class Judge(TimestampedModel):
    """Represents a remote judge worker node."""

    name = models.CharField(max_length=64, unique=True)
    auth_key = models.CharField(max_length=128)
    hostname = models.CharField(max_length=255, blank=True)
    online = models.BooleanField(default=False)
    start_time = models.DateTimeField(null=True, blank=True)
    ping = models.FloatField(null=True, blank=True)
    load = models.FloatField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    problems = models.ManyToManyField("problems.Problem", blank=True, related_name="cached_on_judges")
    runtimes = models.ManyToManyField("judge.Language", blank=True, related_name="judges")
    is_blocked = models.BooleanField(default=False)

    @property
    def uptime(self) -> timedelta | None:
        """Calculate current uptime for online judges.

        Returns:
            Elapsed runtime if start time exists.
        """
        if self.start_time is None:
            return None
        return timezone.now() - self.start_time

    @property
    def status(self) -> str:
        """Compute high-level judge status.

        Returns:
            Effective status code.
        """
        if self.is_blocked:
            return "DI"
        if not self.online:
            return "OF"
        if self.load is not None and self.load >= 0.85:
            return "BU"
        return "AV"

    class Meta(TimestampedModel.Meta):
        db_table = "judge_judge"
        ordering = ["name"]
        verbose_name = "Judge"
        verbose_name_plural = "Judges"
        indexes = [
            models.Index(fields=["name"], name="judge_name_idx"),
            models.Index(fields=["online", "is_blocked"], name="judge_state_idx"),
            models.Index(fields=["created_at"], name="judge_created_idx"),
        ]

    def __str__(self) -> str:
        """Return judge name for admin and logs.

        Returns:
            Unique judge name.
        """
        return self.name
