from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.contests.constants import ParticipationStatus
from core.models import TimestampedModel


class ContestParticipation(TimestampedModel):
    """A user's participation entry in a contest."""

    contest = models.ForeignKey("contests.Contest", on_delete=models.CASCADE, related_name="participations")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="contest_participations")
    status = models.CharField(max_length=16, choices=ParticipationStatus.choices, default=ParticipationStatus.LIVE)
    virtual_start = models.DateTimeField(null=True, blank=True)

    score = models.FloatField(default=0.0)
    cumulative_time = models.DurationField(default=timedelta)
    tiebreaker = models.FloatField(default=0.0)
    is_disqualified = models.BooleanField(default=False)
    format_data = models.JSONField(default=dict)

    class Meta:
        db_table = "contests_participation"
        verbose_name = "Contest Participation"
        verbose_name_plural = "Contest Participations"
        ordering = ["-score", "cumulative_time", "id"]
        unique_together = (("contest", "user", "virtual_start"),)
        indexes = [
            models.Index(fields=["contest", "score"], name="participation_score_idx"),
            models.Index(fields=["contest", "cumulative_time"], name="participation_time_idx"),
        ]

    @property
    def live(self) -> bool:
        """Return whether participation is in live mode."""

        return self.status == ParticipationStatus.LIVE

    @property
    def ended(self) -> bool:
        """Return whether this participation has ended."""

        if self.status != ParticipationStatus.VIRTUAL:
            return self.contest.is_finished
        if not self.virtual_start:
            return False
        if not self.contest.time_limit:
            return self.contest.is_finished
        return timezone.now() >= self.virtual_start + self.contest.time_limit

    @property
    def time_remaining(self) -> timedelta:
        """Return remaining time for virtual participation, zero otherwise."""

        if self.status != ParticipationStatus.VIRTUAL or not self.virtual_start:
            return timedelta(0)
        if not self.contest.time_limit:
            return self.contest.time_remaining
        remaining = (self.virtual_start + self.contest.time_limit) - timezone.now()
        return max(remaining, timedelta(0))

    def __str__(self) -> str:
        """Return readable participation identity."""

        return f"{self.user_id} @ {self.contest.key}"
