from __future__ import annotations

from django.db import models

from core.models import TimestampedModel

class CommentVote(TimestampedModel):
    """A user vote on a comment with +1 or -1 value."""

    UPVOTE = 1
    DOWNVOTE = -1
    VALUE_CHOICES = ((UPVOTE, "Upvote"), (DOWNVOTE, "Downvote"))

    comment = models.ForeignKey(
        "content.Comment",
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    value = models.SmallIntegerField(choices=VALUE_CHOICES)

    class Meta:
        db_table = "content_comment_vote"
        verbose_name = "Comment vote"
        verbose_name_plural = "Comment votes"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["comment", "user"], name="content_vote_comment_user_idx"),
            models.Index(fields=["user"], name="content_vote_user_idx"),
        ]
        unique_together = (("comment", "user"),)

    def __str__(self) -> str:
        """Return a descriptive vote representation."""

        label = "Upvote" if self.value == self.UPVOTE else "Downvote"
        return f"{label} by user {self.user_id} on comment {self.comment_id}"
