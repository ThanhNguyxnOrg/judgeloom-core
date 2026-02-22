"""
JudgeLoom — Rating Signals
=============================

Post-save handler that propagates rating changes from the Rating
model back to the User profile, keeping user.rating and
user.max_rating always up to date.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.ratings.models import Rating
from core.cache import invalidate_pattern, make_key

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Rating)
def sync_user_rating_on_save(
    sender: type[Rating],
    instance: Rating,
    created: bool,
    **kwargs: Any,
) -> None:
    """Update user.rating and user.max_rating from the latest Rating record.

    Uses a queryset update to avoid triggering additional User post_save
    signals (which would cause unnecessary cache invalidation loops).

    Args:
        sender: The Rating model class.
        instance: The rating record that was saved.
        created: Whether this is a new row.
        **kwargs: Extra signal keyword arguments.
    """
    from apps.accounts.models import User

    new_rating = instance.rating_after
    update_fields: dict[str, Any] = {"rating": new_rating}

    current_max = (
        User.objects.filter(pk=instance.user_id)
        .values_list("max_rating", flat=True)
        .first()
    ) or 0

    if new_rating > current_max:
        update_fields["max_rating"] = new_rating

    User.objects.filter(pk=instance.user_id).update(**update_fields)

    invalidate_pattern(make_key("user", instance.user_id))
    logger.debug(
        "Synced rating for user %s: rating=%d (max=%d)",
        instance.user_id,
        new_rating,
        max(new_rating, current_max),
    )
