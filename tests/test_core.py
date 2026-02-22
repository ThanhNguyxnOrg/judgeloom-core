"""
JudgeLoom — Core Module Tests
=================================

Unit tests for core utilities: cache, events, validators,
permissions, pagination, and exceptions.
"""

from __future__ import annotations

import pytest

from core.cache import invalidate_keys, invalidate_pattern, make_key
from core.events import Event
from core.exceptions import (
    JudgeLoomError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)


class TestCacheUtils:
    """Tests for cache utility functions."""

    def test_make_key_simple(self):
        """make_key joins parts with colon prefix."""
        assert make_key("problem", 42) == "jl:problem:42"

    def test_make_key_multiple_parts(self):
        """make_key supports arbitrary depth."""
        assert make_key("contest", "abc", "ranking") == "jl:contest:abc:ranking"

    def test_make_key_single_part(self):
        """make_key with one part."""
        assert make_key("users") == "jl:users"

    def test_invalidate_keys_does_not_raise(self):
        """invalidate_keys runs without error on non-existent keys."""
        invalidate_keys(make_key("nonexistent", "key"))

    def test_invalidate_pattern_does_not_raise(self):
        """invalidate_pattern runs without error (LocMem fallback logs warning)."""
        invalidate_pattern(make_key("test", "prefix"))


class TestEvent:
    """Tests for the Event dataclass."""

    def test_event_creation(self):
        """Event can be created with type and payload."""
        event = Event(type="submission.judged", payload={"id": 1})
        assert event.type == "submission.judged"
        assert event.payload == {"id": 1}

    def test_event_serialize_deserialize(self):
        """Event round-trips through JSON serialization."""
        original = Event(type="contest.started", payload={"key": "abc"})
        serialized = original.serialize()
        restored = Event.deserialize(serialized)
        assert restored.type == original.type
        assert restored.payload == original.payload

    def test_event_immutable(self):
        """Event is frozen (immutable)."""
        event = Event(type="test.event")
        with pytest.raises(AttributeError):
            event.type = "modified"  # type: ignore[misc]

    def test_event_has_timestamp(self):
        """Event auto-generates a timestamp."""
        event = Event(type="test.timestamp")
        assert event.timestamp is not None
        assert len(event.timestamp) > 10


class TestExceptions:
    """Tests for custom exception hierarchy."""

    def test_base_error(self):
        """JudgeLoomError is a proper exception."""
        with pytest.raises(JudgeLoomError):
            raise JudgeLoomError("base error")

    def test_not_found_error(self):
        """NotFoundError inherits from JudgeLoomError."""
        error = NotFoundError("missing")
        assert isinstance(error, JudgeLoomError)

    def test_permission_denied_error(self):
        """PermissionDeniedError inherits from JudgeLoomError."""
        error = PermissionDeniedError("forbidden")
        assert isinstance(error, JudgeLoomError)

    def test_validation_error(self):
        """ValidationError inherits from JudgeLoomError."""
        error = ValidationError("invalid")
        assert isinstance(error, JudgeLoomError)
