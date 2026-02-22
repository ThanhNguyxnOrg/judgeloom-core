from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.content.constants import PostVisibility
from apps.content.models import BlogPost
from core.cache import invalidate_pattern
from core.events import Event, publish_sync


class ContentNotificationService:
    """Service layer for content notification side effects."""

    @staticmethod
    def notify_new_blogpost(blog_post_id: int) -> None:
        """Publish event for a newly published blog post.

        Args:
            blog_post_id: Primary key of the blog post.
        """

        blog_post = BlogPost.objects.select_related("author").filter(id=blog_post_id).first()
        if blog_post is None:
            return

        if blog_post.visibility != PostVisibility.PUBLISHED:
            return

        invalidate_pattern("jl:blog:list")
        invalidate_pattern(f"jl:blog:{blog_post.id}")
        publish_sync(
            Event(
                type="content.blogpost.published",
                payload={
                    "blog_post_id": blog_post.id,
                    "slug": blog_post.slug,
                    "author_id": blog_post.author_id,
                },
            )
        )

    @staticmethod
    def cleanup_old_notifications(retention_days: int = 30) -> int:
        """Remove stale in-cache notification entries by prefix.

        Args:
            retention_days: Retention period in days.

        Returns:
            Count hint for cleanup actions.
        """

        _ = timezone.now() - timedelta(days=retention_days)
        invalidate_pattern("jl:notification:")
        publish_sync(
            Event(
                type="content.notifications.cleaned",
                payload={"retention_days": retention_days},
            )
        )
        return 1
