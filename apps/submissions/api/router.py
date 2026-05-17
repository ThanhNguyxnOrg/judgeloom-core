from __future__ import annotations

from typing import Any

from django.apps import apps
from django.core.paginator import Paginator
from ninja import Router
from ninja.errors import HttpError

from apps.submissions.api.schemas import (
    SubmissionCreateIn,
    SubmissionDetailOut,
    SubmissionPageOut,
    SubmissionSourceOut,
    TestCaseOut,
)
from apps.submissions.models import Submission
from apps.submissions.services import SubmissionService

router = Router(tags=["submissions"])


def _get_problem_model() -> type:
    """Resolve the problem model lazily to avoid import cycles.

    Returns:
        The configured Problem model class.
    """
    return apps.get_model("problems", "Problem")


def _require_authenticated(request: Any) -> None:
    """Ensure request user is authenticated.

    Args:
        request: Incoming Ninja request.

    Raises:
        HttpError: If the user is not authenticated.
    """
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise HttpError(401, "Authentication required.")


@router.get("/", response=SubmissionPageOut)
def list_submissions(
    request: Any,
    user_id: int | None = None,
    problem: str | None = None,
    language: int | None = None,
    result: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> SubmissionPageOut:
    """List submissions with filters and pagination.

    Args:
        request: Incoming Ninja request.
        user_id: Optional owner filter.
        problem: Optional problem code filter.
        language: Optional language id filter.
        result: Optional result code filter.
        page: 1-based page number.
        page_size: Number of items per page.

    Returns:
        Paginated submission list response.
    """
    _require_authenticated(request)

    queryset = Submission.objects.select_related("problem", "language", "user")
    if not request.user.is_staff:
        queryset = queryset.filter(user=request.user)
    elif user_id is not None:
        queryset = queryset.filter(user_id=user_id)

    if problem:
        queryset = queryset.filter(problem__code=problem)
    if language is not None:
        queryset = queryset.filter(language_id=language)
    if result:
        queryset = queryset.filter(result=result)

    paginator = Paginator(queryset.order_by("-created_at"), page_size)
    current_page = paginator.get_page(page)

    items = [
        {
            "id": submission.id,
            "problem_code": submission.problem.code,
            "language": submission.language.name,
            "status": submission.status,
            "result": submission.result,
            "points": submission.points,
            "created_at": submission.created_at,
        }
        for submission in current_page.object_list
    ]
    return SubmissionPageOut(
        page=current_page.number,
        page_size=page_size,
        total=paginator.count,
        items=items,
    )


@router.post("/", response=SubmissionDetailOut)
def create_submission(request: Any, payload: SubmissionCreateIn) -> SubmissionDetailOut:
    """Create a new submission and queue judging.

    Args:
        request: Incoming Ninja request.
        payload: Submission creation input.

    Returns:
        Created submission details.

    Raises:
        HttpError: If problem or language cannot be found.
    """
    _require_authenticated(request)

    Problem = _get_problem_model()  # noqa: N806 — Django model class
    Language = apps.get_model("judge", "Language")

    problem = Problem.objects.filter(code=payload.problem_code).first()
    if problem is None:
        raise HttpError(404, "Problem not found.")

    language = Language.objects.filter(id=payload.language_id).first()
    if language is None:
        raise HttpError(404, "Language not found.")

    submission = SubmissionService.create_submission(
        user=request.user,
        problem=problem,
        language=language,
        source_code=payload.source_code,
    )
    return SubmissionDetailOut(
        id=submission.id,
        user_id=submission.user_id,
        problem_code=submission.problem.code,
        language=submission.language.name,
        status=submission.status,
        result=submission.result,
        points=submission.points,
        time_used=submission.time_used,
        memory_used=submission.memory_used,
        case_total=submission.case_total,
        case_passed=submission.case_passed,
        current_testcase=submission.current_testcase,
        error_message=submission.error_message,
        judged_at=submission.judged_at,
        created_at=submission.created_at,
    )


@router.get("/{submission_id}", response=SubmissionDetailOut)
def get_submission_detail(request: Any, submission_id: int) -> SubmissionDetailOut:
    """Retrieve detailed information about one submission.

    Args:
        request: Incoming Ninja request.
        submission_id: Submission id.

    Returns:
        Submission detail payload.
    """
    _require_authenticated(request)

    submission = SubmissionService.get_submission(submission_id)
    if not SubmissionService.can_view_submission(request.user, submission):
        raise HttpError(403, "You are not allowed to view this submission.")

    return SubmissionDetailOut(
        id=submission.id,
        user_id=submission.user_id,
        problem_code=submission.problem.code,
        language=submission.language.name,
        status=submission.status,
        result=submission.result,
        points=submission.points,
        time_used=submission.time_used,
        memory_used=submission.memory_used,
        case_total=submission.case_total,
        case_passed=submission.case_passed,
        current_testcase=submission.current_testcase,
        error_message=submission.error_message,
        judged_at=submission.judged_at,
        created_at=submission.created_at,
    )


@router.get("/{submission_id}/source", response=SubmissionSourceOut)
def get_submission_source(request: Any, submission_id: int) -> SubmissionSourceOut:
    """Return source code for an authorized submission viewer.

    Args:
        request: Incoming Ninja request.
        submission_id: Submission id.

    Returns:
        Submission source payload.
    """
    _require_authenticated(request)

    submission = SubmissionService.get_submission(submission_id)
    if not SubmissionService.can_view_submission(request.user, submission):
        raise HttpError(403, "You are not allowed to view this source code.")

    return SubmissionSourceOut(submission_id=submission.id, source_code=submission.source.source_code)


@router.get("/{submission_id}/test-cases", response=list[TestCaseOut])
def list_test_case_results(request: Any, submission_id: int) -> list[TestCaseOut]:
    """List per-test-case results for a submission.

    Args:
        request: Incoming Ninja request.
        submission_id: Submission id.

    Returns:
        Ordered list of test-case outputs.
    """
    _require_authenticated(request)

    submission = SubmissionService.get_submission(submission_id)
    if not SubmissionService.can_view_submission(request.user, submission):
        raise HttpError(403, "You are not allowed to view test case data.")

    return [
        TestCaseOut(
            case_number=test_case.case_number,
            status=test_case.status,
            time_used=test_case.time_used,
            memory_used=test_case.memory_used,
            points=test_case.points,
            total_points=test_case.total_points,
            feedback=test_case.feedback,
            output=test_case.output,
            batch_number=test_case.batch_number,
        )
        for test_case in submission.test_cases.all().order_by("case_number")
    ]


@router.post("/{submission_id}/rejudge", response=dict[str, int | str])
def rejudge_submission(request: Any, submission_id: int) -> dict[str, int | str]:
    """Rejudge a submission (staff only).

    Args:
        request: Incoming Ninja request.
        submission_id: Submission id.

    Returns:
        Minimal response confirming queued state.
    """
    _require_authenticated(request)
    if not request.user.is_staff:
        raise HttpError(403, "Staff access required.")

    submission = SubmissionService.get_submission(submission_id)
    SubmissionService.rejudge_submission(submission)
    return {"submission_id": submission.id, "status": submission.status}
