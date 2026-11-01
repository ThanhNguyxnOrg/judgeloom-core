from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Q
from ninja import Query, Router

from apps.problems.api.schemas import (
    ProblemCreateIn,
    ProblemDetailOut,
    ProblemListOut,
    ProblemStatsOut,
    ProblemUpdateIn,
    SolutionIn,
    SolutionOut,
)
from apps.problems.models import Problem, Solution
from apps.problems.services import ProblemService
from core.exceptions import PermissionDeniedError
from core.pagination import PaginationParams, paginate_queryset
from core.permissions import JudgeLoomAuth

if TYPE_CHECKING:
    from django.db.models import QuerySet

router = Router(tags=["problems"])


def _request_user(request: Any) -> Any:
    """Resolve the JWT principal set by JudgeLoomAuth, falling back to session."""

    auth_user = getattr(request, "auth", None)
    if auth_user is not None and getattr(auth_user, "is_authenticated", False):
        return auth_user
    return getattr(request, "user", None)


def _serialize_problem_list(problem: Problem) -> ProblemListOut:
    """Serialize a problem instance for list responses."""

    return ProblemListOut(
        code=problem.code,
        slug=problem.slug,
        name=problem.name,
        difficulty=problem.difficulty,
        points=problem.points,
        visibility=problem.visibility,
        is_public=problem.is_public,
    )


def _serialize_problem_detail(problem: Problem) -> ProblemDetailOut:
    """Serialize a problem instance for detail responses."""

    return ProblemDetailOut(
        code=problem.code,
        slug=problem.slug,
        name=problem.name,
        description=problem.description,
        difficulty=problem.difficulty,
        points=problem.points,
        partial_score=problem.partial_score,
        short_circuit=problem.short_circuit,
        source=problem.source,
        visibility=problem.visibility,
        summary=problem.summary,
        time_limit=problem.time_limit,
        memory_limit=problem.memory_limit,
        types=problem.types,
    )


def _serialize_solution(solution: Solution) -> SolutionOut:
    """Serialize a solution object for API responses."""

    return SolutionOut(
        id=solution.pk,
        problem_code=solution.problem.code,
        author_id=solution.author_id,
        content=solution.content,
        is_public=solution.is_public,
        verdict=solution.verdict,
        created_at=solution.created_at,
    )


@router.get("/", auth=JudgeLoomAuth())
def list_problems(
    request: Any,
    pagination: PaginationParams = Query(...),  # noqa: B008 — Ninja idiom
    difficulty: str | None = None,
    min_points: float | None = None,
    max_points: float | None = None,
    search: str | None = None,
    tag: str | None = None,
    source: str | None = None,
    solved: bool = False,
    ordering: str = "code",
) -> dict[str, Any]:
    """List visible problems with pagination and optional filters."""

    viewer = _request_user(request)
    queryset: QuerySet[Problem] = ProblemService.get_visible_problems(viewer)
    if difficulty:
        queryset = queryset.filter(difficulty=difficulty)
    if min_points is not None:
        queryset = queryset.filter(points__gte=min_points)
    if max_points is not None:
        queryset = queryset.filter(points__lte=max_points)
    if search:
        queryset = queryset.filter(
            Q(code__icontains=search) | Q(name__icontains=search) | Q(summary__icontains=search)
        )
    if tag:
        queryset = queryset.filter(tags__code=tag).distinct()
    if source:
        queryset = queryset.filter(source__icontains=source)
    if solved and getattr(viewer, "is_authenticated", False):
        queryset = queryset.filter(submissions__user=viewer, submissions__result="AC").distinct()

    orderings = {
        "code": "code",
        "-code": "-code",
        "points": "points",
        "-points": "-points",
        "difficulty": "difficulty",
        "-difficulty": "-difficulty",
    }
    queryset = queryset.order_by(orderings.get(ordering, "code"))
    paginated_payload = paginate_queryset(queryset, pagination)
    paginated_payload["results"] = [
        _serialize_problem_list(problem) for problem in paginated_payload["results"]
    ]
    return paginated_payload


@router.post("/", response=ProblemDetailOut, auth=JudgeLoomAuth())
def create_problem(request: Any, payload: ProblemCreateIn) -> ProblemDetailOut:
    """Create a problem as an authenticated user."""

    viewer = _request_user(request)
    if not getattr(viewer, "is_authenticated", False):
        raise PermissionDeniedError("Authentication required.")

    create_kwargs = payload.model_dump(exclude={"code", "name"}, exclude_none=True)
    problem = ProblemService.create_problem(payload.code, payload.name, viewer, **create_kwargs)
    return _serialize_problem_detail(problem)


@router.get("/{code}", response=ProblemDetailOut, auth=JudgeLoomAuth())
def get_problem_detail(request: Any, code: str) -> ProblemDetailOut:
    """Get problem details by problem code."""

    problem = ProblemService.get_problem_by_code(code)
    if not ProblemService.can_see_problem(_request_user(request), problem):
        raise PermissionDeniedError("You do not have access to this problem.")
    return _serialize_problem_detail(problem)


@router.patch("/{code}", response=ProblemDetailOut, auth=JudgeLoomAuth())
def update_problem(request: Any, code: str, payload: ProblemUpdateIn) -> ProblemDetailOut:
    """Update mutable problem fields."""

    problem = ProblemService.get_problem_by_code(code)
    if not ProblemService.can_edit_problem(_request_user(request), problem):
        raise PermissionDeniedError("You do not have permission to edit this problem.")

    update_kwargs = payload.model_dump(exclude_none=True)
    if update_kwargs:
        problem = ProblemService.update_problem(problem, **update_kwargs)
    return _serialize_problem_detail(problem)


@router.get("/{code}/statistics", response=ProblemStatsOut, auth=JudgeLoomAuth())
def get_problem_statistics(request: Any, code: str) -> ProblemStatsOut:
    """Return aggregate statistics for a problem."""

    problem = ProblemService.get_problem_by_code(code)
    if not ProblemService.can_see_problem(_request_user(request), problem):
        raise PermissionDeniedError("You do not have access to this problem.")
    return ProblemStatsOut(**ProblemService.get_problem_statistics(problem))


@router.get("/{code}/solutions", response=list[SolutionOut], auth=JudgeLoomAuth())
def list_solutions(request: Any, code: str) -> list[SolutionOut]:
    """List visible solutions for a given problem."""

    viewer = _request_user(request)
    problem = ProblemService.get_problem_by_code(code)
    if not ProblemService.can_see_problem(viewer, problem):
        raise PermissionDeniedError("You do not have access to this problem.")

    solutions = problem.solutions.select_related("author", "problem")
    if not ProblemService.can_edit_problem(viewer, problem):
        solutions = solutions.filter(is_public=True)

    return [_serialize_solution(solution) for solution in solutions]


@router.post("/{code}/solutions", response=SolutionOut, auth=JudgeLoomAuth())
def create_solution(request: Any, code: str, payload: SolutionIn) -> SolutionOut:
    """Create a new solution for a problem."""

    viewer = _request_user(request)
    problem = ProblemService.get_problem_by_code(code)
    if not ProblemService.can_see_problem(viewer, problem):
        raise PermissionDeniedError("You do not have access to this problem.")
    if not ProblemService.can_edit_problem(viewer, problem):
        raise PermissionDeniedError("Only problem maintainers can publish solutions.")

    solution = Solution.objects.create(
        problem=problem,
        author=viewer,
        content=payload.content,
        is_public=payload.is_public,
        verdict=payload.verdict,
    )
    return _serialize_solution(solution)
