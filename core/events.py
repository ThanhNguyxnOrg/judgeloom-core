"""
JudgeLoom — Core Event System
================================

Lightweight publish/subscribe event bus built on top of Redis pub/sub
via Django Channels.  Services emit domain events (e.g. submission
judged, contest started) and consumers react asynchronously.

This decouples producers from consumers and makes it trivial to add
new side-effects (notifications, cache invalidation, analytics)
without modifying the originating service.

Classes:
    Event: Immutable value object representing a domain event.

Functions:
    publish: Emit an event to a named channel.
    subscribe: Register a callback for events on a channel.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Event:
    """Immutable domain event.

    Attributes:
        type: Dot-notation event type (e.g. ``submission.judged``).
        payload: Arbitrary serializable data attached to the event.
        timestamp: ISO 8601 timestamp (auto-set on creation).
        source: Identifier of the emitting service/module.
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "judgeloom-core"

    def serialize(self) -> str:
        """Serialize the event to a JSON string.

        Returns:
            JSON representation of all event fields.
        """
        return json.dumps(asdict(self))

    @classmethod
    def deserialize(cls, data: str) -> Event:
        """Reconstruct an event from a JSON string.

        Args:
            data: JSON string produced by ``serialize()``.

        Returns:
            A new Event instance.
        """
        return cls(**json.loads(data))


def _derive_channel(event: Event) -> str:
    """Derive a channel group name from an event type.

    Uses the top-level namespace of the dot-notation event type.
    For example, ``submission.judged`` yields ``"submissions"``.

    Args:
        event: The event whose type determines the channel.

    Returns:
        Channel group name.
    """
    namespace = event.type.split(".")[0]
    # Pluralise simple namespace (e.g. "submission" → "submissions")
    if not namespace.endswith("s"):
        namespace += "s"
    return namespace


async def publish(event: Event, *, channel: str | None = None) -> None:
    """Publish an event to a Django Channels group.

    All consumers subscribed to the named group will receive the event.
    This is non-blocking and uses the configured channel layer
    (Redis in production, in-memory in development/testing).

    Args:
        event: The event to broadcast.
        channel: Optional explicit channel group name.  When omitted the
            channel is derived from the event type namespace.
    """
    from channels.layers import get_channel_layer

    resolved_channel = channel or _derive_channel(event)
    layer = get_channel_layer()
    if layer is None:
        logger.warning("No channel layer configured — event dropped: %s", event.type)
        return

    await layer.group_send(
        resolved_channel,
        {
            "type": "event.broadcast",
            "data": event.serialize(),
        },
    )
    logger.debug("Published %s to channel '%s'", event.type, resolved_channel)


def publish_sync(event: Event, *, channel: str | None = None) -> None:
    """Synchronous wrapper around ``publish()`` for use in Django views / services.

    Uses ``asgiref.sync.async_to_sync`` to bridge the sync/async boundary.

    Args:
        event: The event to broadcast.
        channel: Optional explicit channel group name.
    """
    from asgiref.sync import async_to_sync

    async_to_sync(publish)(event, channel=channel)


# ─── Event Type Constants ─────────────────────────────────────────────────
# Centralised constants prevent typo-driven bugs in publishers/subscribers.

SUBMISSION_CREATED = "submission.created"
SUBMISSION_JUDGING = "submission.judging"
SUBMISSION_JUDGED = "submission.judged"
SUBMISSION_REJUDGED = "submission.rejudged"

CONTEST_STARTED = "contest.started"
CONTEST_ENDED = "contest.ended"
CONTEST_PARTICIPATION_JOINED = "contest.participation.joined"
CONTEST_RANKING_UPDATED = "contest.ranking.updated"

PROBLEM_CREATED = "problem.created"
PROBLEM_UPDATED = "problem.updated"

USER_REGISTERED = "user.registered"
USER_RATING_CHANGED = "user.rating_changed"
