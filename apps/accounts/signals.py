"""
JudgeLoom — Account Signals
===============================

Handles post-save events for User model: logs new registrations
and invalidates profile caches on updates.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User
from core.cache import invalidate_pattern, make_key

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def handle_user_post_save(
    sender: type[User],
    instance: User,
    created: bool,
    **kwargs: Any,
) -> None:
    """Log new user registrations and invalidate profile cache on changes.

    Args:
        sender: The User model class.
        instance: The user that was saved.
        created: Whether this is a new row.
        **kwargs: Extra signal keyword arguments.
    """
    if created:
        logger.info(
            "New user registered: %s (pk=%s, role=%s)",
            instance.username,
            instance.pk,
            instance.role,
        )
    else:
        invalidate_pattern(make_key("user", instance.pk))
        logger.debug("User %s profile updated — cache invalidated", instance.pk)
