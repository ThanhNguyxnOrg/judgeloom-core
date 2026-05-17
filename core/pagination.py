"""
JudgeLoom — Core Pagination
==============================

Cursor and offset pagination utilities for Django Ninja endpoints.
Uses platform-wide defaults from ``settings.JUDGELOOM``.

Classes:
    PaginationParams: Query parameter schema for paginated endpoints.
    PagedResponse: Generic paginated response wrapper.

Functions:
    paginate_queryset: Apply pagination to a Django QuerySet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from django.conf import settings
from ninja import Field, Schema

if TYPE_CHECKING:
    from django.db.models import QuerySet

T = TypeVar("T")

_defaults = settings.JUDGELOOM


class PaginationParams(Schema):
    """Query parameters for paginated list endpoints.

    Attributes:
        page: 1-based page number.
        page_size: Number of items per page (capped by MAX_PAGE_SIZE).
    """

    page: int = Field(default=1, ge=1, description="Page number (1-indexed).")
    page_size: int = Field(
        default=_defaults["DEFAULT_PAGE_SIZE"],
        ge=1,
        le=_defaults["MAX_PAGE_SIZE"],
        description="Items per page.",
    )


class PagedResponse[T](Schema):
    """Wrapper for paginated API responses.

    Attributes:
        count: Total number of items matching the query.
        page: Current page number.
        page_size: Number of items returned in this page.
        total_pages: Total number of pages.
        results: The items for this page.
    """

    count: int
    page: int
    page_size: int
    total_pages: int
    results: list[Any]


def paginate_queryset(
    queryset: QuerySet,  # type: ignore[type-arg]
    params: PaginationParams,
) -> dict[str, Any]:
    """Slice a queryset according to pagination parameters.

    Args:
        queryset: The full (unpaginated) queryset.
        params: Pagination parameters from the request.

    Returns:
        A dictionary matching the ``PagedResponse`` schema with keys
        ``count``, ``page``, ``page_size``, ``total_pages``, and ``results``.
    """
    total = queryset.count()
    total_pages = max(1, (total + params.page_size - 1) // params.page_size)

    # Clamp page to valid range
    page = min(max(params.page, 1), total_pages)

    offset = (page - 1) * params.page_size
    items = list(queryset[offset : offset + params.page_size])

    return {
        "count": total,
        "page": page,
        "page_size": params.page_size,
        "total_pages": total_pages,
        "results": items,
    }
