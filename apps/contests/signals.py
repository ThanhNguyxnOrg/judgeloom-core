"""
JudgeLoom — Contest Signals
==============================

Cache invalidation handlers for contest and participation models.
Ensures that list/detail views and ranking caches stay fresh when
contest configuration or participation data changes.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.contests.models import Contest, ContestParticipation
from core.cache import invalidate_pattern, make_key

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Contest)
def invalidate_contest_cache_on_save(
    sender: type[Contest],
    instance: Contest,
    created: bool,
    **kwargs: Any,
) -> None:
    """Invalidate contest list and detail caches after save.

    Args:
        sender: The Contest model class.
        instance: The contest that was saved.
        created: Whether this is a new row.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("contest", "list"))
    invalidate_pattern(make_key("contest", instance.pk))
    action = "Created" if created else "Updated"
    logger.debug("%s contest %s — cache invalidated", action, instance.key)


@receiver(post_delete, sender=Contest)
def invalidate_contest_cache_on_delete(
    sender: type[Contest],
    instance: Contest,
    **kwargs: Any,
) -> None:
    """Invalidate contest caches after deletion.

    Args:
        sender: The Contest model class.
        instance: The contest being deleted.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("contest", "list"))
    invalidate_pattern(make_key("contest", instance.pk))
    logger.debug("Deleted contest %s — cache invalidated", instance.key)


@receiver(post_save, sender=ContestParticipation)
def invalidate_ranking_cache_on_participation(
    sender: type[ContestParticipation],
    instance: ContestParticipation,
    created: bool,
    **kwargs: Any,
) -> None:
    """Invalidate ranking cache when participation data changes.

    This fires on both new participations (join) and score updates
    from the grading pipeline.

    Args:
        sender: The ContestParticipation model class.
        instance: The participation record that was saved.
        created: Whether this is a new row.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("contest", instance.contest_id, "ranking"))
    logger.debug(
        "Participation %s for contest %s — ranking cache invalidated",
        instance.pk,
        instance.contest_id,
    )
