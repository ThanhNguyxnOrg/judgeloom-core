from __future__ import annotations

from typing import Any

from ninja import Router

from apps.problems.api.schemas import ProblemListOut
from apps.tags.api.schemas import TagDetailOut, TagIn, TagOut
from apps.tags.models import Tag
from apps.tags.services import TagService
from core.exceptions import PermissionDeniedError
from core.permissions import JudgeLoomAuth, is_staff

router = Router(tags=["tags"])

def _serialize_problem(problem: Any) -> ProblemListOut:
    """Serialize problem shape used by tag detail endpoint."""

    return ProblemListOut(
        code=problem.code,
        slug=problem.slug,
        name=problem.name,
        difficulty=problem.difficulty,
        points=problem.points,
        visibility=problem.visibility,
        is_public=problem.is_public,
    )

def _serialize_tag(tag: Tag) -> TagOut:
    """Serialize tag list output."""

    return TagOut(name=tag.name, code=tag.code, problem_count=tag.problem_count)

@router.get("/", response=list[TagOut], auth=JudgeLoomAuth())
def list_tags(request: Any) -> list[TagOut]:
    """List tags ordered by popularity then alphabetically."""

    _ = request
    tags = TagService.get_popular_tags(limit=200)
    return [_serialize_tag(tag) for tag in tags]

@router.get("/{code}", response=TagDetailOut, auth=JudgeLoomAuth())
def get_tag_detail(request: Any, code: str) -> TagDetailOut:
    """Get a tag and visible problems linked to it."""

    tag = Tag.objects.get(code=code)
    problems = TagService.get_problems_by_tag(code, request.user)
    return TagDetailOut(
        name=tag.name,
        code=tag.code,
        problem_count=tag.problem_count,
        problems=[_serialize_problem(problem) for problem in problems],
    )

@router.post("/", response=TagOut, auth=JudgeLoomAuth())
def create_tag(request: Any, payload: TagIn) -> TagOut:
    """Create a new tag. Staff users only."""

    if not is_staff(request.user):
        raise PermissionDeniedError("Only staff users can create tags.")

    tag = TagService.get_or_create_tag(payload.name)
    return _serialize_tag(tag)
