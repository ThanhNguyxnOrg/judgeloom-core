"""
JudgeLoom — Core Exceptions
==============================

Application-level exception hierarchy and Django Ninja error handler
registration. All service-layer errors should subclass ``JudgeLoomError``
so the API layer can produce consistent JSON error responses.

Exception Hierarchy::

    JudgeLoomError
    ├── NotFoundError
    ├── PermissionDeniedError
    ├── ValidationError
    ├── RateLimitError
    ├── SubmissionError
    │   ├── CompilationError
    │   └── JudgeUnavailableError
    └── ContestError
        ├── ContestNotActiveError
        └── ContestAccessDeniedError
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.http import JsonResponse

if TYPE_CHECKING:
    from django.http import HttpRequest
    from ninja import NinjaAPI


class JudgeLoomError(Exception):
    """Base exception for all JudgeLoom business-logic errors.

    Attributes:
        message: Human-readable error description.
        code: Machine-readable error code for clients.
        status_code: HTTP status code for the response.
        details: Optional additional context for debugging.
    """

    message: str = "An unexpected error occurred."
    code: str = "error"
    status_code: int = 400
    details: dict[str, Any] | None = None

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        if details is not None:
            self.details = details
        super().__init__(self.message)

    def as_response_body(self) -> dict[str, Any]:
        """Serialize the error for JSON API responses.

        Returns:
            Dictionary with ``error``, ``code``, and optional ``details`` keys.
        """
        body: dict[str, Any] = {
            "error": self.message,
            "code": self.code,
        }
        if self.details:
            body["details"] = self.details
        return body


# ─── Generic Errors ────────────────────────────────────────────────────────


class NotFoundError(JudgeLoomError):
    """Raised when a requested resource does not exist."""

    message = "The requested resource was not found."
    code = "not_found"
    status_code = 404


class PermissionDeniedError(JudgeLoomError):
    """Raised when the user lacks permission for an action."""

    message = "You do not have permission to perform this action."
    code = "permission_denied"
    status_code = 403


class ValidationError(JudgeLoomError):
    """Raised when input data fails validation."""

    message = "The provided data is invalid."
    code = "validation_error"
    status_code = 422


class RateLimitError(JudgeLoomError):
    """Raised when the user exceeds a rate limit."""

    message = "Rate limit exceeded. Please try again later."
    code = "rate_limit_exceeded"
    status_code = 429


# ─── Submission Errors ─────────────────────────────────────────────────────


class SubmissionError(JudgeLoomError):
    """Base exception for submission-related failures."""

    message = "An error occurred while processing the submission."
    code = "submission_error"


class CompilationError(SubmissionError):
    """Raised when source code fails to compile."""

    message = "Compilation failed."
    code = "compilation_error"


class JudgeUnavailableError(SubmissionError):
    """Raised when no judge is available to process a submission."""

    message = "No judge is currently available. Please try again shortly."
    code = "judge_unavailable"
    status_code = 503


class JudgeJobConflictError(JudgeLoomError):
    """Raised when a judge job is stale, expired, or no longer active."""

    message = "The judge job is no longer available."
    code = "judge_job_conflict"
    status_code = 409


# ─── Contest Errors ────────────────────────────────────────────────────────


class ContestError(JudgeLoomError):
    """Base exception for contest-related failures."""

    message = "An error occurred with the contest operation."
    code = "contest_error"


class ContestNotActiveError(ContestError):
    """Raised when an action requires the contest to be active."""

    message = "This contest is not currently active."
    code = "contest_not_active"


class ContestAccessDeniedError(ContestError):
    """Raised when the user cannot access a contest."""

    message = "You do not have access to this contest."
    code = "contest_access_denied"
    status_code = 403


# ─── Django Ninja Error Handler Registration ──────────────────────────────


def configure_api_exception_handlers(api: NinjaAPI) -> None:
    """Register exception handlers on the NinjaAPI instance.

    This should be called once during URL configuration to ensure all
    ``JudgeLoomError`` subclasses are caught and returned as structured
    JSON responses.

    Args:
        api: The NinjaAPI instance to attach handlers to.
    """

    @api.exception_handler(JudgeLoomError)
    def handle_judgeloom_error(
        request: HttpRequest,
        exc: JudgeLoomError,
    ) -> JsonResponse:
        return JsonResponse(exc.as_response_body(), status=exc.status_code)

    @api.exception_handler(Exception)
    def handle_unexpected_error(
        request: HttpRequest,
        exc: Exception,
    ) -> JsonResponse:
        import logging

        logger = logging.getLogger("apps")
        logger.exception("Unhandled exception in API: %s", exc)
        return JsonResponse(
            {"error": "An internal server error occurred.", "code": "internal_error"},
            status=500,
        )
