from __future__ import annotations

from typing import Any

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.problems.api.schemas import ProblemListOut
from apps.tags.api.schemas import TagDetailOut, TagIn, TagOut
from apps.tags.models import Tag
from apps.tags.services import TagService
from core.exceptions import PermissionDeniedError
from core.permissions import JudgeLoomAuth

router = Router(tags=["tags"])


def _request_user(request: Any) -> Any:
    """Resolve the JWT principal set by JudgeLoomAuth, falling back to session."""

    auth_user = getattr(request, "auth", None)
    if auth_user is not None and getattr(auth_user, "is_authenticated", False):
        return auth_user
    return getattr(request, "user", None)


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

    return TagOut(
        name=tag.name,
        code=tag.code,
        problem_count=getattr(tag, "problem_total", tag.problem_count),
    )


@router.get("/", response=list[TagOut], auth=JudgeLoomAuth())
def list_tags(request: Any) -> list[TagOut]:
    """List tags ordered by popularity then alphabetically."""

    tags = TagService.get_popular_tags(limit=200, user=_request_user(request))
    return [_serialize_tag(tag) for tag in tags]


@router.get("/{code}", response=TagDetailOut, auth=JudgeLoomAuth())
def get_tag_detail(request: Any, code: str) -> TagDetailOut:
    """Get a tag and visible problems linked to it."""

    viewer = _request_user(request)
    tag = get_object_or_404(Tag, code=code)
    problems = list(TagService.get_problems_by_tag(code, viewer))
    return TagDetailOut(
        name=tag.name,
        code=tag.code,
        problem_count=len(problems),
        problems=[_serialize_problem(problem) for problem in problems],
    )


@router.post("/", response=TagOut, auth=JudgeLoomAuth())
def create_tag(request: Any, payload: TagIn) -> TagOut:
    """Create a new tag. Staff users only."""

    viewer = _request_user(request)
    if not getattr(viewer, "is_staff", False):
        raise PermissionDeniedError("Only staff users can create tags.")

    tag = TagService.get_or_create_tag(payload.name)
    return _serialize_tag(tag)
