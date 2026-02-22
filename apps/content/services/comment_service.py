from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import F, QuerySet

from apps.content.constants import CommentVisibility
from apps.content.models import BlogPost, Comment, CommentVote
from core.exceptions import ValidationError

class CommentService:
    """Business operations for threaded comments."""

    SEGMENT_WIDTH = 3
    MAX_DEPTH = 10
    MAX_SEGMENT_VALUE = 999

    @classmethod
    @transaction.atomic
    def create_comment(
        cls,
        post: BlogPost,
        author: Any,
        body: str,
        parent: Comment | None = None,
    ) -> Comment:
        """Create a threaded comment and generate materialized path.

        Args:
            post: Target post.
            author: Comment author.
            body: Comment text.
            parent: Parent comment for replies.

        Returns:
            The created comment.

        Raises:
            ValidationError: If parent is invalid or depth is exceeded.
        """

        if parent is not None and parent.post_id != post.id:
            raise ValidationError("Parent comment does not belong to this post.")

        if parent is None:
            sibling_paths = list(
                Comment.objects.select_for_update()
                .filter(post=post, parent__isnull=True)
                .values_list("path", flat=True)
            )
            segment = cls._next_segment(sibling_paths)
            new_path = segment
        else:
            if parent.depth >= cls.MAX_DEPTH:
                raise ValidationError("Maximum comment depth reached.")
            sibling_paths = list(
                Comment.objects.select_for_update()
                .filter(post=post, parent=parent)
                .values_list("path", flat=True)
            )
            segment = cls._next_segment(sibling_paths)
            new_path = f"{parent.path}.{segment}"

        return Comment.objects.create(
            post=post,
            author=author,
            parent=parent,
            body=body,
            path=new_path,
            visibility=CommentVisibility.VISIBLE,
        )

    @staticmethod
    def edit_comment(comment: Comment, body: str) -> Comment:
        """Edit an existing comment body.

        Args:
            comment: Comment to modify.
            body: New body text.

        Returns:
            The updated comment.
        """

        comment.body = body
        comment.save(update_fields=["body", "updated_at"])
        return comment

    @staticmethod
    def delete_comment(comment: Comment) -> Comment:
        """Soft delete a comment.

        Args:
            comment: Comment to soft-delete.

        Returns:
            Updated comment marked as deleted.
        """

        comment.visibility = CommentVisibility.DELETED
        comment.body = "[deleted]"
        comment.save(update_fields=["visibility", "body", "updated_at"])
        return comment

    @staticmethod
    @transaction.atomic
    def vote_comment(comment: Comment, user: Any, value: int) -> None:
        """Upsert a vote and maintain denormalized comment score.

        Args:
            comment: Voted comment.
            user: Voting user.
            value: Vote direction (+1 or -1).

        Raises:
            ValidationError: If vote value is outside allowed values.
        """

        if value not in (CommentVote.UPVOTE, CommentVote.DOWNVOTE):
            raise ValidationError("Vote value must be +1 or -1.")

        vote, created = CommentVote.objects.select_for_update().get_or_create(
            comment=comment,
            user=user,
            defaults={"value": value},
        )

        if created:
            score_delta = value
        elif vote.value == value:
            score_delta = 0
        else:
            score_delta = value - vote.value
            vote.value = value
            vote.save(update_fields=["value", "updated_at"])

        if score_delta:
            Comment.objects.filter(id=comment.id).update(score=F("score") + score_delta)
            comment.refresh_from_db(fields=["score"])

    @staticmethod
    def get_comments_for_post(post: BlogPost) -> QuerySet[Comment]:
        """Return comments for a post in threaded display order.

        Args:
            post: Target post.

        Returns:
            QuerySet ordered by materialized path.
        """

        return (
            Comment.objects.select_related("author", "parent")
            .filter(post=post)
            .order_by("path")
        )

    @classmethod
    def get_comment_tree(cls, post: BlogPost) -> list[dict[str, Any]]:
        """Build a nested tree structure for all post comments.

        Args:
            post: Target post.

        Returns:
            Nested list of comment dictionaries.
        """

        comments = list(cls.get_comments_for_post(post))
        nodes: dict[int, dict[str, Any]] = {}
        roots: list[dict[str, Any]] = []

        for comment in comments:
            node = {
                "id": comment.id,
                "post_id": comment.post_id,
                "author_id": comment.author_id,
                "parent_id": comment.parent_id,
                "path": comment.path,
                "body": comment.body,
                "visibility": comment.visibility,
                "score": comment.score,
                "created_at": comment.created_at,
                "updated_at": comment.updated_at,
                "children": [],
            }
            nodes[comment.id] = node

            if comment.parent_id is None:
                roots.append(node)
            else:
                parent = nodes.get(comment.parent_id)
                if parent is None:
                    roots.append(node)
                else:
                    parent["children"].append(node)

        return roots

    @classmethod
    def _next_segment(cls, sibling_paths: list[str]) -> str:
        """Compute the next 3-digit path segment among siblings.

        Args:
            sibling_paths: Existing sibling paths.

        Returns:
            Next zero-padded 3-digit segment.

        Raises:
            ValidationError: If segment space is exhausted.
        """

        if not sibling_paths:
            return "001"

        current_max = 0
        for sibling_path in sibling_paths:
            last_segment = sibling_path.split(".")[-1]
            try:
                numeric_value = int(last_segment)
            except ValueError as exc:
                raise ValidationError("Invalid comment path segment encountered.") from exc
            current_max = max(current_max, numeric_value)

        next_value = current_max + 1
        if next_value > cls.MAX_SEGMENT_VALUE:
            raise ValidationError("Too many sibling comments at this depth.")
        return f"{next_value:0{cls.SEGMENT_WIDTH}d}"
