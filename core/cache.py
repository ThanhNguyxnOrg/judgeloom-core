"""
JudgeLoom — Core Cache Utilities
==================================

Cache key builders and invalidation helpers.  All cache keys follow
the pattern ``jl:<domain>:<identifier>`` to avoid collisions and
make bulk invalidation straightforward.

Functions:
    make_key: Build a namespaced cache key.
    cached_queryset: Cache a queryset result for a given TTL.
    invalidate_pattern: Delete all cache keys matching a prefix.
"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache


def make_key(*parts: str | int) -> str:
    """Build a colon-separated, namespaced cache key.

    Args:
        *parts: Segments of the key (e.g. ``"problem"``, ``42``).

    Returns:
        A string like ``"jl:problem:42"``.

    Examples:
        >>> make_key("problem", 42)
        'jl:problem:42'
        >>> make_key("contest", "abc", "ranking")
        'jl:contest:abc:ranking'
    """
    return "jl:" + ":".join(str(p) for p in parts)


def cached_queryset(
    key: str,
    queryset_fn: Any,
    timeout: int = 300,
) -> Any:
    """Execute and cache a queryset-producing callable.

    If the result is already in cache, return it without hitting
    the database.  Otherwise, call ``queryset_fn()``, store the
    result, and return it.

    Args:
        key: Full cache key (use ``make_key`` to build it).
        queryset_fn: A zero-argument callable that returns a list or
            queryset.  Will only be called on cache miss.
        timeout: Cache TTL in seconds.  Defaults to 300 (5 minutes).

    Returns:
        The cached or freshly computed result.
    """
    result = cache.get(key)
    if result is not None:
        return result
    result = queryset_fn()
    cache.set(key, result, timeout)
    return result


def invalidate_pattern(prefix: str) -> None:
    """Delete all cache keys that start with the given prefix.

    This uses Django's cache ``delete_pattern`` if available (django-redis),
    otherwise falls back to a no-op with a warning.

    Args:
        prefix: The key prefix to match (e.g. ``"jl:problem:42"``).
    """
    delete_pattern = getattr(cache, "delete_pattern", None)
    if callable(delete_pattern):
        delete_pattern(f"{prefix}*")
    else:
        import logging

        logging.getLogger(__name__).warning(
            "Cache backend does not support delete_pattern. Key prefix '%s' was NOT invalidated.",
            prefix,
        )


def invalidate_keys(*keys: str) -> None:
    """Delete specific cache keys.

    Args:
        *keys: One or more full cache keys to remove.
    """
    cache.delete_many(list(keys))
