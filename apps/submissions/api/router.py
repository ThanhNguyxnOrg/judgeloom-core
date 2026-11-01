from __future__ import annotations

from typing import Any

from django.apps import apps
from django.core.paginator import Paginator
from ninja import Router
from ninja.errors import HttpError
from ninja.security import SessionAuth

from apps.judge.models import Judge
from apps.judge.services.shadow_job_service import ShadowJobService
from apps.submissions.api.schemas import (
    ShadowJobCreateIn,
    ShadowJobOut,
    SubmissionCreateIn,
    SubmissionDetailOut,
    SubmissionPageOut,
    SubmissionRunIn,
    SubmissionShareOut,
    SubmissionSourceOut,
    SubmissionVisibilityIn,
    TestCaseOut,
)
from apps.submissions.constants import SubmissionMode
from apps.submissions.models import Submission
from apps.submissions.services import SubmissionService
from core.permissions import JudgeLoomAuth

router = Router(tags=["submissions"])


def _get_problem_model() -> type:
    """Resolve the problem model lazily to avoid import cycles.

    Returns:
        The configured Problem model class.
    """
    return apps.get_model("problems", "Problem")


_JWT_AUTH = JudgeLoomAuth()


def _request_user(request: Any) -> Any:
    """Resolve the JWT principal, falling back to the session user."""

    auth_user = getattr(request, "auth", None)
    if auth_user is not None and getattr(auth_user, "is_authenticated", False):
        return auth_user

    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        return user

    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        jwt_user = _JWT_AUTH.authenticate(request, token)
        if jwt_user is not None:
            return jwt_user
    return user


def _require_authenticated(request: Any) -> None:
    """Ensure request user is authenticated.

    Args:
        request: Incoming Ninja request.

    Raises:
        HttpError: If the user is not authenticated.
    """
    user = _request_user(request)
    if not getattr(user, "is_authenticated", False):
        raise HttpError(401, "Authentication required.")


def _submission_detail_out(submission: Any, *, include_private: bool) -> SubmissionDetailOut:
    """Serialize a submission, masking source-bearing error text for public readers."""

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
        mode=submission.mode,
        is_public=submission.is_public,
        error_message=submission.error_message if include_private else "",
        judged_at=submission.judged_at,
        created_at=submission.created_at,
    )


@router.get("/", response=SubmissionPageOut, auth=[JudgeLoomAuth(), SessionAuth()])
def list_submissions(
    request: Any,
    user_id: int | None = None,
    problem: str | None = None,
    language: int | None = None,
    result: str | None = None,
    public: bool = False,
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

    queryset = Submission.objects.select_related("problem", "language", "user").filter(mode=SubmissionMode.SUBMIT)
    if not _request_user(request).is_staff:
        queryset = queryset.filter(is_public=True) if public else queryset.filter(user=_request_user(request))
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
            "is_public": submission.is_public,
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


@router.post("/", response=SubmissionDetailOut, auth=[JudgeLoomAuth(), SessionAuth()])
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
        user=_request_user(request),
        problem=problem,
        language=language,
        source_code=payload.source_code,
    )
    return _submission_detail_out(submission, include_private=True)


@router.post("/run", response=SubmissionDetailOut, auth=[JudgeLoomAuth(), SessionAuth()])
def run_submission(request: Any, payload: SubmissionRunIn) -> SubmissionDetailOut:
    """Execute source against custom stdin without scoring or rating."""

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
        user=_request_user(request),
        problem=problem,
        language=language,
        source_code=payload.source_code,
        mode=SubmissionMode.RUN,
        custom_input=payload.stdin,
        expected_output=payload.expected_output,
    )
    return _submission_detail_out(submission, include_private=True)


@router.get("/shared/{token}", response=SubmissionDetailOut)
def get_shared_submission(request: Any, token: str) -> SubmissionDetailOut:
    """Return metadata for a submission share token."""

    submission = SubmissionService.get_submission_by_share_token(token)
    if submission is None:
        raise HttpError(404, "Shared submission not found.")
    return _submission_detail_out(submission, include_private=False)


@router.patch(
    "/{submission_id}/visibility",
    response=SubmissionDetailOut,
    auth=[JudgeLoomAuth(), SessionAuth()],
)
def set_submission_visibility(
    request: Any,
    submission_id: int,
    payload: SubmissionVisibilityIn,
) -> SubmissionDetailOut:
    """Set the public metadata flag for an owned submission."""

    _require_authenticated(request)
    submission = SubmissionService.get_submission(submission_id)
    if not SubmissionService.can_edit_submission(_request_user(request), submission):
        raise HttpError(403, "You are not allowed to change this submission.")
    submission = SubmissionService.set_submission_public(submission, payload.is_public)
    return _submission_detail_out(submission, include_private=True)


@router.post(
    "/{submission_id}/share",
    response=SubmissionShareOut,
    auth=[JudgeLoomAuth(), SessionAuth()],
)
def create_submission_share(request: Any, submission_id: int) -> SubmissionShareOut:
    """Issue a metadata-only share token for an owned submission."""

    _require_authenticated(request)
    submission = SubmissionService.get_submission(submission_id)
    if not SubmissionService.can_edit_submission(_request_user(request), submission):
        raise HttpError(403, "You are not allowed to share this submission.")
    submission = SubmissionService.create_share_token(submission)
    return SubmissionShareOut(share_token=str(submission.share_token))


@router.delete("/{submission_id}/share", auth=[JudgeLoomAuth(), SessionAuth()])
def revoke_submission_share(request: Any, submission_id: int) -> dict[str, str]:
    """Revoke the current share token for an owned submission."""

    _require_authenticated(request)
    submission = SubmissionService.get_submission(submission_id)
    if not SubmissionService.can_edit_submission(_request_user(request), submission):
        raise HttpError(403, "You are not allowed to share this submission.")
    SubmissionService.revoke_share_token(submission)
    return {"detail": "Share token revoked."}


def _shadow_job_out(job: Any) -> ShadowJobOut:
    return ShadowJobOut(
        id=job.id,
        submission_id=job.submission_id,
        status=job.status,
        target_judge=job.target_judge.name if job.target_judge is not None else None,
        claimed_by=job.claimed_by.name if job.claimed_by is not None else None,
        result=job.result,
        total_points=job.total_points,
        case_total=job.case_total,
        case_passed=job.case_passed,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
    )


@router.post(
    "/{submission_id}/shadow",
    response=ShadowJobOut,
    auth=[JudgeLoomAuth(), SessionAuth()],
)
def create_shadow_job(request: Any, submission_id: int, payload: ShadowJobCreateIn) -> ShadowJobOut:
    """Queue a staff-only non-scoring replay of a submission."""

    _require_authenticated(request)
    if not _request_user(request).is_staff:
        raise HttpError(403, "Staff access required.")

    submission = SubmissionService.get_submission(submission_id)
    target_judge = None
    if payload.judge_name:
        target_judge = Judge.objects.filter(name=payload.judge_name).first()
        if target_judge is None:
            raise HttpError(404, "Judge not found.")

    try:
        job = ShadowJobService.create_for_submission(submission, target_judge=target_judge)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    return _shadow_job_out(job)


@router.get(
    "/{submission_id}/shadows",
    response=list[ShadowJobOut],
    auth=[JudgeLoomAuth(), SessionAuth()],
)
def list_shadow_jobs(request: Any, submission_id: int) -> list[ShadowJobOut]:
    """List staff-only replay jobs for a submission."""

    _require_authenticated(request)
    if not _request_user(request).is_staff:
        raise HttpError(403, "Staff access required.")

    submission = SubmissionService.get_submission(submission_id)
    jobs = submission.shadow_jobs.select_related("target_judge", "claimed_by").order_by("-created_at")
    return [_shadow_job_out(job) for job in jobs]


@router.get("/{submission_id}", response=SubmissionDetailOut)
def get_submission_detail(request: Any, submission_id: int) -> SubmissionDetailOut:
    """Retrieve detailed information about one submission.

    Args:
        request: Incoming Ninja request.
        submission_id: Submission id.

    Returns:
        Submission detail payload.
    """
    submission = SubmissionService.get_submission(submission_id)
    if not SubmissionService.can_view_submission(_request_user(request), submission):
        raise HttpError(403, "You are not allowed to view this submission.")

    include_private = SubmissionService.can_view_submission_private(_request_user(request), submission)
    return _submission_detail_out(submission, include_private=include_private)


@router.get(
    "/{submission_id}/source",
    response=SubmissionSourceOut,
    auth=[JudgeLoomAuth(), SessionAuth()],
)
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
    if not SubmissionService.can_view_submission_private(_request_user(request), submission):
        raise HttpError(403, "You are not allowed to view this source code.")

    return SubmissionSourceOut(submission_id=submission.id, source_code=submission.source.source_code)


@router.get(
    "/{submission_id}/test-cases",
    response=list[TestCaseOut],
    auth=[JudgeLoomAuth(), SessionAuth()],
)
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
    if not SubmissionService.can_view_submission_private(_request_user(request), submission):
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


@router.post(
    "/{submission_id}/rejudge",
    response=dict[str, int | str],
    auth=[JudgeLoomAuth(), SessionAuth()],
)
def rejudge_submission(request: Any, submission_id: int) -> dict[str, int | str]:
    """Rejudge a submission (staff only).

    Args:
        request: Incoming Ninja request.
        submission_id: Submission id.

    Returns:
        Minimal response confirming queued state.
    """
    _require_authenticated(request)
    if not _request_user(request).is_staff:
        raise HttpError(403, "Staff access required.")

    submission = SubmissionService.get_submission(submission_id)
    SubmissionService.rejudge_submission(submission)
    return {"submission_id": submission.id, "status": submission.status}
