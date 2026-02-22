"""
JudgeLoom — Organization Signals
====================================

Cache invalidation for organization list and detail views.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.organizations.models import Organization
from core.cache import invalidate_pattern, make_key

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Organization)
def invalidate_org_cache_on_save(
    sender: type[Organization],
    instance: Organization,
    created: bool,
    **kwargs: Any,
) -> None:
    """Invalidate organization caches after creation or update.

    Args:
        sender: The Organization model class.
        instance: The organization that was saved.
        created: Whether this is a new row.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("org", "list"))
    invalidate_pattern(make_key("org", instance.pk))
    action = "Created" if created else "Updated"
    logger.debug("%s organization %s — cache invalidated", action, instance.name)


@receiver(post_delete, sender=Organization)
def invalidate_org_cache_on_delete(
    sender: type[Organization],
    instance: Organization,
    **kwargs: Any,
) -> None:
    """Invalidate organization caches after deletion.

    Args:
        sender: The Organization model class.
        instance: The organization being deleted.
        **kwargs: Extra signal keyword arguments.
    """
    invalidate_pattern(make_key("org", "list"))
    invalidate_pattern(make_key("org", instance.pk))
    logger.debug("Deleted organization %s — cache invalidated", instance.name)
