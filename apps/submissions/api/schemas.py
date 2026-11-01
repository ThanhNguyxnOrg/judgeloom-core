from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves this at runtime

from ninja import Schema


class SubmissionCreateIn(Schema):
    """Input payload for creating a submission."""

    problem_code: str
    language_id: int
    source_code: str


class SubmissionRunIn(Schema):
    """Input payload for a custom-input run."""

    problem_code: str
    language_id: int
    source_code: str
    stdin: str = ""
    expected_output: str = ""


class SubmissionListOut(Schema):
    """Compact submission representation for list endpoints."""

    id: int
    problem_code: str
    language: str
    status: str
    result: str | None
    points: float
    is_public: bool
    created_at: datetime


class SubmissionVisibilityIn(Schema):
    """Owner-controlled metadata visibility."""

    is_public: bool


class SubmissionShareOut(Schema):
    """Share-link token response."""

    share_token: str


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
    mode: str
    is_public: bool
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


class ShadowJobCreateIn(Schema):
    """Optional judge target for a replay."""

    judge_name: str | None = None


class ShadowJobOut(Schema):
    """Shadow/replay job status and result."""

    id: int
    submission_id: int
    status: str
    target_judge: str | None
    claimed_by: str | None
    result: str
    total_points: float
    case_total: int
    case_passed: int
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class SubmissionPageOut(Schema):
    """Paginated submissions response."""

    page: int
    page_size: int
    total: int
    items: list[SubmissionListOut]
