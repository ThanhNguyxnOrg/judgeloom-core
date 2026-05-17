from __future__ import annotations

from typing import TYPE_CHECKING

from ninja import Schema

if TYPE_CHECKING:
    from datetime import datetime


class SubmissionCreateIn(Schema):
    """Input payload for creating a submission."""

    problem_code: str
    language_id: int
    source_code: str


class SubmissionListOut(Schema):
    """Compact submission representation for list endpoints."""

    id: int
    problem_code: str
    language: str
    status: str
    result: str | None
    points: float
    created_at: datetime


class SubmissionDetailOut(Schema):
    """Detailed submission response."""

    id: int
    user_id: int
    problem_code: str
    language: str
    status: str
    result: str | None
    points: float
    time_used: float
    memory_used: int
    case_total: int
    case_passed: int
    current_testcase: int
    error_message: str
    judged_at: datetime | None
    created_at: datetime


class SubmissionSourceOut(Schema):
    """Submission source code payload."""

    submission_id: int
    source_code: str


class TestCaseOut(Schema):
    """Submission test-case result payload."""

    case_number: int
    status: str
    time_used: float
    memory_used: int
    points: float
    total_points: float
    feedback: str
    output: str
    batch_number: int | None


class SubmissionPageOut(Schema):
    """Paginated submissions response."""

    page: int
    page_size: int
    total: int
    items: list[SubmissionListOut]
