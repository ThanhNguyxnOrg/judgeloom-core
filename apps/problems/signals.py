"""
JudgeLoom — Problem Signals
===============================

Cache invalidation for problem list and detail views whenever
a problem record is created, updated, or deleted.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.problems.models import Problem
from core.cache import invalidate_pattern, make_key

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Problem)
def invalidate_problem_cache_on_save(
    sender: type[Problem],
    instance: Problem,
    created: bool,
    **kwargs: Any,
) -> None:
    """Invalidate problem caches after creation or update.

    Args:
        sender: The Problem model class.
        instance: The problem that was saved.
        created: Whether this is a new row.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("problem", "list"))
    invalidate_pattern(make_key("problem", instance.pk))
    action = "Created" if created else "Updated"
    logger.debug("%s problem %s — cache invalidated", action, instance.code)


@receiver(post_delete, sender=Problem)
def invalidate_problem_cache_on_delete(
    sender: type[Problem],
    instance: Problem,
    **kwargs: Any,
) -> None:
    """Invalidate problem caches after deletion.

    Args:
        sender: The Problem model class.
        instance: The problem being deleted.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("problem", "list"))
    invalidate_pattern(make_key("problem", instance.pk))
    logger.debug("Deleted problem %s — cache invalidated", instance.code)
