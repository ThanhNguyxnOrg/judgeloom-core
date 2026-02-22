from __future__ import annotations

from django.db import models

from apps.content.constants import CommentVisibility
from core.models import TimestampedModel

class Comment(TimestampedModel):
    """Threaded comment using a materialized path."""

    post = models.ForeignKey(
        "content.BlogPost",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField()
    visibility = models.CharField(
        max_length=16,
        choices=CommentVisibility.choices,
        default=CommentVisibility.VISIBLE,
    )
    score = models.IntegerField(default=0)
    path = models.CharField(max_length=255)

    @property
    def is_visible(self) -> bool:
        """Return True when the comment is visible to users."""

        return self.visibility == CommentVisibility.VISIBLE

    @property
    def depth(self) -> int:
        """Return path depth for rendering indentation."""

        if not self.path:
            return 0
        return len(self.path.split("."))

    @property
    def is_root(self) -> bool:
        """Return True when the comment has no parent."""

        return self.parent_id is None

    class Meta:
        db_table = "content_comment"
        verbose_name = "Comment"
        verbose_name_plural = "Comments"
        ordering = ("path",)
        indexes = [
            models.Index(fields=["post", "path"], name="content_cmt_post_path_idx"),
            models.Index(fields=["author"], name="content_cmt_author_idx"),
        ]

    def __str__(self) -> str:
        """Return a compact comment descriptor."""

        return f"Comment #{self.pk} by {self.author_id} on {self.post_id}"
