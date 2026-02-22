from __future__ import annotations

from datetime import datetime

from ninja import Schema

class ProblemCreateIn(Schema):
    """Input payload for creating a new problem."""

    code: str
    name: str
    description: str
    difficulty: str | None = None
    points: float = 0.0
    partial_score: bool = False
    short_circuit: bool = False
    source: str = ""
    visibility: str = "private"
    summary: str = ""
    time_limit: float | None = None
    memory_limit: int | None = None

class ProblemUpdateIn(Schema):
    """Input payload for updating problem fields."""

    name: str | None = None
    description: str | None = None
    difficulty: str | None = None
    points: float | None = None
    partial_score: bool | None = None
    short_circuit: bool | None = None
    source: str | None = None
    visibility: str | None = None
    summary: str | None = None
    time_limit: float | None = None
    memory_limit: int | None = None

class ProblemListOut(Schema):
    """Compact problem representation for listing endpoints."""

    code: str
    slug: str
    name: str
    difficulty: str | None
    points: float
    visibility: str
    is_public: bool

class ProblemDetailOut(Schema):
    """Detailed representation for a single problem."""

    code: str
    slug: str
    name: str
    description: str
    difficulty: str | None
    points: float
    partial_score: bool
    short_circuit: bool
    source: str
    visibility: str
    summary: str
    time_limit: float
    memory_limit: int
    types: list[str]

class ProblemStatsOut(Schema):
    """Response schema for problem statistics."""

    problem_code: str
    total_submissions: int
    total_public_solutions: int
    total_accepted: int
    total_partial: int
    total_wrong: int
    accepted_rate: float

class SolutionIn(Schema):
    """Input payload for creating a solution."""

    content: str
    is_public: bool = False
    verdict: str | None = None

class SolutionOut(Schema):
    """API representation of a solution."""

    id: int
    problem_code: str
    author_id: int
    content: str
    is_public: bool
    verdict: str | None
    created_at: datetime
