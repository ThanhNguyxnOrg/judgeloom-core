from __future__ import annotations

from typing import TYPE_CHECKING

from ninja import Schema

if TYPE_CHECKING:
    from datetime import datetime


class RatingOut(Schema):
    """Rating transition representation."""

    user_id: int
    contest_key: str
    rank: int
    rating_before: int
    rating_after: int
    delta: int
    performance: int


class RatingHistoryOut(Schema):
    """User rating history row."""

    contest_key: str
    contest_name: str
    rank: int
    rating_before: int
    rating_after: int
    delta: int
    created_at: datetime


class RatingChangeOut(Schema):
    """Contest rating change row."""

    user_id: int
    username: str
    rank: int
    rating_before: int
    rating_after: int
    delta: int
    performance: int
