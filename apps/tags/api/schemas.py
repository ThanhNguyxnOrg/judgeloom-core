from __future__ import annotations

from typing import TYPE_CHECKING

from ninja import Schema

if TYPE_CHECKING:
    from apps.problems.api.schemas import ProblemListOut


class TagIn(Schema):
    """Input payload for creating tags."""

    name: str


class TagOut(Schema):
    """Compact tag representation."""

    name: str
    code: str
    problem_count: int


class TagDetailOut(Schema):
    """Detailed tag representation with linked problems."""

    name: str
    code: str
    problem_count: int
    problems: list[ProblemListOut]
