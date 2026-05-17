from __future__ import annotations

from django.db import models

from core.models import TimestampedModel


class Rating(TimestampedModel):
    """Stores per-contest rating transition for a participant."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="ratings")
    contest = models.ForeignKey("contests.Contest", on_delete=models.CASCADE, related_name="ratings")
    participation = models.OneToOneField(
        "contests.ContestParticipation", on_delete=models.CASCADE, related_name="rating"
    )

    rank = models.PositiveIntegerField()
    rating_before = models.IntegerField()
    rating_after = models.IntegerField()
    volatility_before = models.IntegerField(default=0)
    volatility_after = models.IntegerField(default=0)
    performance = models.IntegerField(default=0)

    class Meta:
        db_table = "ratings_rating"
        verbose_name = "Rating"
        verbose_name_plural = "Ratings"
        ordering = ["-created_at"]
        unique_together = (("user", "contest"),)
        indexes = [
            models.Index(fields=["contest", "rank"], name="rating_contest_rank_idx"),
            models.Index(fields=["user", "created_at"], name="rating_user_created_idx"),
        ]

    def __str__(self) -> str:
        """Return concise rating change representation."""

        delta = self.rating_after - self.rating_before
        return f"{self.user_id}@{self.contest_id}: {delta:+d}"
