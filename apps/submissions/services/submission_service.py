from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.models import Submission, SubmissionSource, SubmissionTestCase
from core.events import (
    SUBMISSION_CREATED,
    SUBMISSION_JUDGED,
    SUBMISSION_JUDGING,
    SUBMISSION_REJUDGED,
    Event,
    publish_sync,
)
from core.exceptions import NotFoundError, SubmissionError
from core.validators import validate_source_code_size

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.judge.models import Language


class SubmissionService:
    """Service layer for submission creation, querying, and judge updates."""

    @classmethod
    def create_submission(
        cls,
        user: Any,
        problem: Any,
        language: Language,
        source_code: str,
        contest_participation: Any | None = None,
    ) -> Submission:
        """Create a submission and enqueue it for judging.

        Args:
            user: Authenticated user creating the submission.
            problem: Target problem instance.
            language: Selected language.
            source_code: Submitted source code.
            contest_participation: Optional contest participation object.

        Returns:
            Persisted submission instance.

        Raises:
            SubmissionError: If validation fails.
        """
        validate_source_code_size(source_code)
        cls._validate_language(problem=problem, language=language)
        cls._check_rate_limit(user=user)

        with transaction.atomic():
            submission = Submission.objects.create(
                user=user,
                problem=problem,
                language=language,
                contest_participation=contest_participation,
                status=SubmissionStatus.QUEUED,
            )
            SubmissionSource.objects.create(submission=submission, source_code=source_code)

        cls._publish_event(SUBMISSION_CREATED, {"submission_id": submission.id, "status": submission.status})

        from apps.submissions.tasks import judge_submission

        cast("Any", judge_submission).delay(submission.id)
        return submission

    @classmethod
    def get_submission(cls, submission_id: int) -> Submission:
        """Fetch a submission by id.

        Args:
            submission_id: Submission primary key.

        Returns:
            Matching submission instance.

        Raises:
            NotFoundError: If the submission does not exist.
        """
        submission = (
            Submission.objects.select_related("user", "problem", "language", "judged_on")
            .filter(id=submission_id)
            .first()
        )
        if submission is None:
            raise NotFoundError(f"Submission {submission_id} was not found.")
        return submission

    @classmethod
    def get_user_submissions(cls, user: Any, problem: Any | None = None) -> QuerySet[Submission]:
        """Return submissions visible to the user, optionally filtered by problem.

        Args:
            user: User requesting submissions.
            problem: Optional problem instance.

        Returns:
            Queryset of submissions ordered by recency.
        """
        queryset = Submission.objects.select_related("problem", "language", "judged_on").all()
        if not getattr(user, "is_staff", False):
            queryset = queryset.filter(user=user)
        if problem is not None:
            queryset = queryset.filter(problem=problem)
        return queryset

    @classmethod
    def can_view_submission(cls, user: Any, submission: Submission) -> bool:
        """Evaluate whether a user can view a submission.

        Args:
            user: User attempting to view the submission.
            submission: Submission under evaluation.

        Returns:
            True if access is permitted.
        """
        if not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False):
            return True
        if submission.user_id == user.id:
            return True
        author_id = getattr(submission.problem, "author_id", None) or getattr(
            submission.problem,
            "created_by_id",
            None,
        )
        return author_id == user.id

    @classmethod
    def rejudge_submission(cls, submission: Submission) -> None:
        """Reset a submission and enqueue it for rejudging.

        Args:
            submission: Submission to reset and queue.
        """
        submission.status = SubmissionStatus.QUEUED
        submission.result = None
        submission.points = 0.0
        submission.time_used = 0.0
        submission.memory_used = 0
        submission.case_total = 0
        submission.case_passed = 0
        submission.current_testcase = 0
        submission.error_message = ""
        submission.judged_at = None
        submission.save(
            update_fields=[
                "status",
                "result",
                "points",
                "time_used",
                "memory_used",
                "case_total",
                "case_passed",
                "current_testcase",
                "error_message",
                "judged_at",
                "updated_at",
            ]
        )
        submission.test_cases.all().delete()

        cls._publish_event(SUBMISSION_REJUDGED, {"submission_id": submission.id})

        from apps.submissions.tasks import judge_submission

        cast("Any", judge_submission).delay(submission.id)

    @classmethod
    def rejudge_problem(cls, problem: Any) -> int:
        """Rejudge all submissions for a problem.

        Args:
            problem: Problem instance.

        Returns:
            Number of queued submissions.
        """
        submission_ids = list(Submission.objects.filter(problem=problem).values_list("id", flat=True))
        if not submission_ids:
            return 0

        Submission.objects.filter(id__in=submission_ids).update(
            status=SubmissionStatus.QUEUED,
            result=None,
            points=0.0,
            time_used=0.0,
            memory_used=0,
            case_total=0,
            case_passed=0,
            current_testcase=0,
            error_message="",
            judged_at=None,
            judged_on=None,
        )
        SubmissionTestCase.objects.filter(submission_id__in=submission_ids).delete()

        from apps.submissions.tasks import rejudge_submissions

        cast("Any", rejudge_submissions).delay(submission_ids)
        return len(submission_ids)

    @classmethod
    def update_submission_result(cls, submission_id: int, result_data: dict[str, Any]) -> Submission:
        """Apply final result payload received from a judge.

        Args:
            submission_id: Submission primary key.
            result_data: Judge payload containing aggregate metrics.

        Returns:
            Updated submission instance.

        Raises:
            NotFoundError: If the submission does not exist.
        """
        with transaction.atomic():
            submission = Submission.objects.select_for_update().filter(id=submission_id).first()
            if submission is None:
                raise NotFoundError(f"Submission {submission_id} was not found.")

            status_value = str(result_data.get("status", SubmissionStatus.COMPLETED))
            result_value = result_data.get("result")
            if result_value and result_value not in SubmissionResult.values:
                result_value = SubmissionResult.IE

            submission.status = status_value
            submission.result = result_value
            submission.points = float(result_data.get("points", submission.points))
            submission.time_used = float(result_data.get("time_used", submission.time_used))
            submission.memory_used = int(result_data.get("memory_used", submission.memory_used))
            submission.case_total = int(result_data.get("case_total", submission.case_total))
            submission.case_passed = int(result_data.get("case_passed", submission.case_passed))
            submission.current_testcase = int(result_data.get("current_testcase", submission.current_testcase))
            submission.error_message = str(result_data.get("error_message", submission.error_message))
            submission.judged_at = timezone.now()
            submission.save()

        payload = {
            "submission_id": submission.id,
            "status": submission.status,
            "result": submission.result,
            "points": submission.points,
            "time_used": submission.time_used,
            "memory_used": submission.memory_used,
            "case_total": submission.case_total,
            "case_passed": submission.case_passed,
        }
        cls._publish_event(SUBMISSION_JUDGED, payload)
        cls._broadcast(submission.id, payload)
        return submission

    @classmethod
    def update_test_case_result(
        cls,
        submission_id: int,
        case_data: dict[str, Any],
    ) -> SubmissionTestCase:
        """Apply per-test-case update from a judge.

        Args:
            submission_id: Submission primary key.
            case_data: Judge payload for a single test case.

        Returns:
            Upserted submission test-case record.

        Raises:
            NotFoundError: If the submission does not exist.
        """
        case_number = int(case_data.get("case_number", 0))
        status_value = str(case_data.get("status", SubmissionResult.IR))
        if status_value not in SubmissionResult.values:
            status_value = SubmissionResult.IR

        with transaction.atomic():
            submission = Submission.objects.select_for_update().filter(id=submission_id).first()
            if submission is None:
                raise NotFoundError(f"Submission {submission_id} was not found.")

            test_case, _created = SubmissionTestCase.objects.update_or_create(
                submission=submission,
                case_number=case_number,
                defaults={
                    "status": status_value,
                    "time_used": float(case_data.get("time_used", 0.0)),
                    "memory_used": int(case_data.get("memory_used", 0)),
                    "points": float(case_data.get("points", 0.0)),
                    "total_points": float(case_data.get("total_points", 0.0)),
                    "feedback": str(case_data.get("feedback", "")),
                    "output": str(case_data.get("output", "")),
                    "batch_number": case_data.get("batch_number"),
                },
            )

            submission.current_testcase = max(submission.current_testcase, case_number)
            incoming_case_total = int(case_data.get("case_total", submission.case_total or 0))
            submission.case_total = max(submission.case_total, incoming_case_total, case_number)
            submission.case_passed = SubmissionTestCase.objects.filter(
                submission=submission,
                status=SubmissionResult.AC,
            ).count()
            submission.status = SubmissionStatus.JUDGING
            submission.save(
                update_fields=[
                    "current_testcase",
                    "case_total",
                    "case_passed",
                    "status",
                    "updated_at",
                ]
            )

        payload = {
            "submission_id": submission.id,
            "case_number": test_case.case_number,
            "status": test_case.status,
            "case_total": submission.case_total,
            "case_passed": submission.case_passed,
            "current_testcase": submission.current_testcase,
        }
        cls._publish_event(SUBMISSION_JUDGING, payload)
        cls._broadcast(submission.id, payload)
        return test_case

    @classmethod
    def _validate_language(cls, problem: Any, language: Language) -> None:
        """Validate language availability and problem compatibility.

        Args:
            problem: Problem instance.
            language: Language selected by user.

        Raises:
            SubmissionError: If language is disabled or unsupported for the problem.
        """
        if not language.is_enabled:
            raise SubmissionError("Selected language is disabled.")

        allowed_relations = ["allowed_languages", "languages", "runtimes"]
        for relation in allowed_relations:
            manager = getattr(problem, relation, None)
            if manager is None or not hasattr(manager, "exists"):
                continue
            if manager.exists() and not manager.filter(id=language.id).exists():
                raise SubmissionError("Selected language is not allowed for this problem.")
            return

    @classmethod
    def _check_rate_limit(cls, user: Any) -> None:
        """Enforce per-user submission rate limit.

        Args:
            user: User creating a submission.

        Raises:
            SubmissionError: If user exceeds configured limit.
        """
        if getattr(user, "is_staff", False):
            return

        limit = int(getattr(settings, "SUBMISSION_RATE_LIMIT_PER_MINUTE", 30))
        window_start = timezone.now() - timedelta(minutes=1)
        recent_count = Submission.objects.filter(user=user, created_at__gte=window_start).count()
        if recent_count >= limit:
            raise SubmissionError("Submission rate limit exceeded. Try again shortly.")

    @classmethod
    def _publish_event(cls, event_type: str, payload: dict[str, Any]) -> None:
        """Publish a domain event through the configured event bus.

        Args:
            event_type: Event type constant (e.g. ``SUBMISSION_CREATED``).
            payload: Event payload data.
        """
        publish_sync(Event(type=event_type, payload=payload))

    @classmethod
    def _broadcast(cls, submission_id: int, payload: dict[str, Any]) -> None:
        """Push a realtime update to submission WebSocket listeners.

        Args:
            submission_id: Submission primary key.
            payload: Serialized event payload.
        """
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f"submission_{submission_id}",
            {"type": "broadcast", "payload": payload},
        )
