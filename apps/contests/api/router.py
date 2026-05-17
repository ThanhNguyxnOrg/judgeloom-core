from __future__ import annotations

from typing import Any

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.contests.api.schemas import (
    ContestCreateIn,
    ContestDetailOut,
    ContestListOut,
    ContestProblemIn,
    ContestProblemOut,
    ContestUpdateIn,
    ParticipationOut,
    RankingEntryOut,
)
from apps.contests.models import Contest, ContestParticipation
from apps.contests.services.contest_service import ContestService
from apps.contests.services.ranking_service import RankingService
from core.exceptions import ContestAccessDeniedError
from core.pagination import PaginationParams, paginate_queryset
from core.permissions import is_authenticated, is_staff

router = Router(tags=["contests"])


@router.get("/", response=list[ContestListOut])
def list_contests(request, page: int = 1, page_size: int = 20) -> list[dict[str, Any]]:
    """List contests visible to the requesting user."""

    queryset = ContestService.get_visible_contests(request.user)
    paginated = paginate_queryset(queryset, PaginationParams(page=page, page_size=page_size))
    rows = paginated.get("items", []) if isinstance(paginated, dict) else paginated

    return [
        {
            "id": contest.id,
            "key": contest.key,
            "name": contest.name,
            "start_time": contest.start_time,
            "end_time": contest.end_time,
            "visibility": contest.visibility,
            "is_rated": contest.is_rated,
            "format_name": contest.format_name,
        }
        for contest in rows
    ]


@router.post("/", response=ContestDetailOut)
def create_contest(request, payload: ContestCreateIn) -> dict[str, Any]:
    """Create a contest. Staff-only endpoint."""

    if not is_staff(request):
        raise ContestAccessDeniedError("Only staff can create contests.")

    contest = ContestService.create_contest(
        name=payload.name,
        key=payload.key,
        organizer=request.user,
        start_time=payload.start_time,
        end_time=payload.end_time,
        description=payload.description,
        visibility=payload.visibility,
        is_rated=payload.is_rated,
        time_limit=payload.time_limit,
        format_name=payload.format_name,
        format_config=payload.format_config,
    )
    return _contest_detail_dict(contest)


@router.get("/{key}", response=ContestDetailOut)
def contest_detail(request, key: str) -> dict[str, Any]:
    """Get contest detail by key."""

    contest = get_object_or_404(Contest, key=key)
    if not ContestService.can_see_contest(request.user, contest):
        raise ContestAccessDeniedError("You are not allowed to view this contest.")
    return _contest_detail_dict(contest)


@router.patch("/{key}", response=ContestDetailOut)
def update_contest(request, key: str, payload: ContestUpdateIn) -> dict[str, Any]:
    """Update contest fields."""

    contest = get_object_or_404(Contest, key=key)
    if not ContestService.is_contest_staff(request.user, contest):
        raise ContestAccessDeniedError("You are not contest staff.")

    updates = payload.model_dump(exclude_none=True)
    contest = ContestService.update_contest(contest, **updates)
    return _contest_detail_dict(contest)


@router.get("/{key}/problems", response=list[ContestProblemOut])
def list_contest_problems(request, key: str) -> list[dict[str, Any]]:
    """List problems in a contest."""

    contest = get_object_or_404(Contest, key=key)
    if not ContestService.can_see_contest(request.user, contest):
        raise ContestAccessDeniedError("You are not allowed to view this contest.")

    return [
        {
            "id": cp.id,
            "problem_id": cp.problem_id,
            "label": cp.label,
            "order": cp.order,
            "points": cp.points,
            "partial_score": cp.partial_score,
        }
        for cp in contest.contest_problems.select_related("problem").all()
    ]


@router.post("/{key}/problems", response=ContestProblemOut)
def add_contest_problem(request, key: str, payload: ContestProblemIn) -> dict[str, Any]:
    """Add a problem to a contest."""

    contest = get_object_or_404(Contest, key=key)
    if not ContestService.is_contest_staff(request.user, contest):
        raise ContestAccessDeniedError("You are not contest staff.")

    from django.apps import apps

    problem_model = apps.get_model("problems", "Problem")
    problem = get_object_or_404(problem_model, pk=payload.problem_id)

    contest_problem = ContestService.add_problem(
        contest=contest,
        problem=problem,
        label=payload.label,
        points=payload.points,
        order=payload.order or (contest.contest_problems.count() + 1),
        partial_score=payload.partial_score,
        output_prefix_override=payload.output_prefix_override,
        max_submissions=payload.max_submissions,
    )

    return {
        "id": contest_problem.id,
        "problem_id": contest_problem.problem_id,
        "label": contest_problem.label,
        "order": contest_problem.order,
        "points": contest_problem.points,
        "partial_score": contest_problem.partial_score,
    }


@router.get("/{key}/ranking", response=list[RankingEntryOut])
def get_ranking(request, key: str, frozen: bool = True) -> list[dict[str, Any]]:
    """Get contest ranking; optionally apply freeze display."""

    contest = get_object_or_404(Contest, key=key)
    if not ContestService.can_see_contest(request.user, contest):
        raise ContestAccessDeniedError("You are not allowed to view this contest.")

    if frozen:
        return RankingService.get_frozen_ranking(contest)
    return RankingService.get_contest_ranking(contest)


@router.post("/{key}/join", response=ParticipationOut)
def join_contest(request, key: str, access_code: str | None = None) -> dict[str, Any]:
    """Join contest as live participant."""

    if not is_authenticated(request):
        raise ContestAccessDeniedError("Authentication required.")

    contest = get_object_or_404(Contest, key=key)
    participation = ContestService.join_contest(contest, request.user, access_code=access_code)
    return _participation_dict(participation)


@router.post("/{key}/virtual", response=ParticipationOut)
def start_virtual(request, key: str) -> dict[str, Any]:
    """Start virtual participation for authenticated user."""

    if not is_authenticated(request):
        raise ContestAccessDeniedError("Authentication required.")

    contest = get_object_or_404(Contest, key=key)
    participation = ContestService.start_virtual(contest, request.user)
    return _participation_dict(participation)


@router.get("/{key}/participations", response=list[ParticipationOut])
def list_participations(request, key: str) -> list[dict[str, Any]]:
    """List participations in a contest."""

    contest = get_object_or_404(Contest, key=key)
    if not ContestService.is_contest_staff(request.user, contest):
        raise ContestAccessDeniedError("Contest staff access required.")

    return [_participation_dict(item) for item in contest.participations.select_related("user").all()]


@router.get("/{key}/participations/{user_id}", response=ParticipationOut)
def participation_detail(request, key: str, user_id: int) -> dict[str, Any]:
    """Return one user's participation details for contest."""

    contest = get_object_or_404(Contest, key=key)
    if not ContestService.is_contest_staff(request.user, contest) and request.user.id != user_id:
        raise ContestAccessDeniedError("Not allowed to view this participation.")

    participation = get_object_or_404(ContestParticipation, contest=contest, user_id=user_id)
    return _participation_dict(participation)


def _contest_detail_dict(contest: Contest) -> dict[str, Any]:
    """Build API detail payload for contest."""

    return {
        "id": contest.id,
        "key": contest.key,
        "name": contest.name,
        "description": contest.description,
        "start_time": contest.start_time,
        "end_time": contest.end_time,
        "visibility": contest.visibility,
        "is_rated": contest.is_rated,
        "format_name": contest.format_name,
        "is_active": contest.is_active,
        "is_finished": contest.is_finished,
        "is_upcoming": contest.is_upcoming,
        "points_precision": contest.points_precision,
    }


def _participation_dict(participation: ContestParticipation) -> dict[str, Any]:
    """Build API payload for participation."""

    return {
        "id": participation.id,
        "user_id": participation.user_id,
        "contest_id": participation.contest_id,
        "status": participation.status,
        "virtual_start": participation.virtual_start,
        "score": float(participation.score),
        "cumulative_time_seconds": participation.cumulative_time.total_seconds(),
        "tiebreaker": float(participation.tiebreaker),
        "is_disqualified": participation.is_disqualified,
        "format_data": participation.format_data,
    }
