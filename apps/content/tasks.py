from __future__ import annotations

from celery import shared_task

from apps.content.services.content_notification_service import ContentNotificationService


@shared_task(
    bind=True,
    name="content.notify_new_blogpost",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def notify_new_blogpost(self: object, blog_post_id: int) -> None:
    """Publish and invalidate side effects for a new blog post.

    Args:
        self: Celery task instance.
        blog_post_id: Primary key of the blog post.
    """

    ContentNotificationService.notify_new_blogpost(blog_post_id)


@shared_task(
    bind=True,
    name="content.cleanup_old_notifications",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def cleanup_old_notifications(self: object, retention_days: int = 30) -> int:
    """Clean up old notification data.

    Args:
        self: Celery task instance.
        retention_days: Number of days to keep notifications.

    Returns:
        Count hint of cleanup actions.
    """

    return ContentNotificationService.cleanup_old_notifications(retention_days)
