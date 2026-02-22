"""
JudgeLoom — Content Signals
===============================

Cache invalidation for blog posts.  Ensures the blog listing and
individual post caches stay fresh when content is published,
updated, or removed.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.content.models import BlogPost
from core.cache import invalidate_pattern, make_key

logger = logging.getLogger(__name__)


@receiver(post_save, sender=BlogPost)
def invalidate_blog_cache_on_save(
    sender: type[BlogPost],
    instance: BlogPost,
    created: bool,
    **kwargs: Any,
) -> None:
    """Invalidate blog list and detail caches after save.

    Args:
        sender: The BlogPost model class.
        instance: The post that was saved.
        created: Whether this is a new row.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("blog", "list"))
    invalidate_pattern(make_key("blog", instance.pk))
    action = "Created" if created else "Updated"
    logger.debug("%s blog post %s — cache invalidated", action, instance.pk)


@receiver(post_delete, sender=BlogPost)
def invalidate_blog_cache_on_delete(
    sender: type[BlogPost],
    instance: BlogPost,
    **kwargs: Any,
) -> None:
    """Invalidate blog caches after deletion.

    Args:
        sender: The BlogPost model class.
        instance: The post being deleted.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("blog", "list"))
    invalidate_pattern(make_key("blog", instance.pk))
    logger.debug("Deleted blog post %s — cache invalidated", instance.pk)
