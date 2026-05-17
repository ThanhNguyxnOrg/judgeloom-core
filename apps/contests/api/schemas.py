from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ninja import Schema

if TYPE_CHECKING:
    from datetime import datetime, timedelta


class ContestCreateIn(Schema):
    """Input payload for contest creation."""

    name: str
    key: str
    description: str = ""
    start_time: datetime
    end_time: datetime
    visibility: str = "private"
    is_rated: bool = False
    time_limit: timedelta | None = None
    format_name: str = "default"
    format_config: dict[str, Any] = {}


class ContestUpdateIn(Schema):
    """Input payload for contest partial updates."""

    name: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    visibility: str | None = None
    is_rated: bool | None = None
    format_name: str | None = None
    format_config: dict[str, Any] | None = None
    access_code: str | None = None


class ContestListOut(Schema):
    """Minimal contest representation for list views."""

    id: int
    key: str
    name: str
    start_time: datetime
    end_time: datetime
    visibility: str
    is_rated: bool
    format_name: str


class ContestDetailOut(ContestListOut):
    """Detailed contest response schema."""

    description: str
    is_active: bool
    is_finished: bool
    is_upcoming: bool
    points_precision: int


class ContestProblemIn(Schema):
    """Input payload for adding a problem to contest."""

    problem_id: int
    label: str
    points: float
    order: int | None = None
    partial_score: bool = False
    output_prefix_override: int | None = None
    max_submissions: int | None = None


class ContestProblemOut(Schema):
    """Contest problem representation."""

    id: int
    problem_id: int
    label: str
    order: int
    points: float
    partial_score: bool


class RankingEntryOut(Schema):
    """Ranking row representation."""

    rank: int
    user_id: int
    username: str
    score: float
    tiebreaker: float
    format_data: dict[str, Any]


class ParticipationOut(Schema):
    """Contest participation representation."""

    id: int
    user_id: int
    contest_id: int
    status: str
    virtual_start: datetime | None
    score: float
    cumulative_time_seconds: float
    tiebreaker: float
    is_disqualified: bool
    format_data: dict[str, Any]
