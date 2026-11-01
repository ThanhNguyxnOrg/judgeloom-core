from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves this at runtime

from ninja import Schema


class RatingOut(Schema):
    """Rating transition representation."""

    user_id: int
    contest_key: str
    rank: int
    rating_before: int
    rating_after: int
    delta: int
    performance: float


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
    performance: float
