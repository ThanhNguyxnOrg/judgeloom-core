from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.judge.models import JudgeJob, JudgeJobStatus
from apps.submissions.constants import SubmissionMode, SubmissionResult, SubmissionStatus
from apps.submissions.models import Submission, SubmissionSource, SubmissionTestCase
from core.events import (
    SUBMISSION_JUDGED,
    SUBMISSION_JUDGING,
    SUBMISSION_STATUS,
    Event,
    publish_sync,
)
from core.exceptions import NotFoundError, SubmissionError
from core.validators import validate_source_code_size

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.judge.models import Language

MAX_RUN_INPUT_BYTES = 64 * 1024


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
        mode: str = SubmissionMode.SUBMIT,
        custom_input: str = "",
    ) -> Submission:
        """Create a submission or ephemeral run and enqueue it for judging.

        Args:
            user: Authenticated user creating the request.
            problem: Target problem instance.
            language: Selected language.
            source_code: Submitted source code.
            contest_participation: Optional contest participation object.
            mode: ``submit`` for scored submissions or ``run`` for custom input.
            custom_input: Standard input for a run.

        Returns:
            Persisted submission instance.

        Raises:
            SubmissionError: If validation fails.
        """
        validate_source_code_size(source_code)
        if mode == SubmissionMode.RUN:
            if len(custom_input.encode("utf-8")) > MAX_RUN_INPUT_BYTES:
                raise SubmissionError("Custom input exceeds the maximum allowed size.")
        elif custom_input:
            raise SubmissionError("Custom input is only valid for runs.")
        cls._validate_problem_access(user=user, problem=problem)
        cls._validate_language(problem=problem, language=language)
        if mode == SubmissionMode.RUN:
            cls._check_run_rate_limit(user=user)
        else:
            cls._check_rate_limit(user=user)

        package = problem.packages.filter(is_active=True).first()
        if package is None and mode != SubmissionMode.RUN:
            raise SubmissionError("No active test data package is available for this problem.")

        config = cls._build_job_config(
            problem=problem,
            language=language,
            package=package,
            contest_participation=contest_participation,
            mode=mode,
            custom_input=custom_input,
        )

        with transaction.atomic():
            submission = Submission.objects.create(
                user=user,
                problem=problem,
                language=language,
                contest_participation=contest_participation,
                mode=mode,
                custom_input=custom_input,
                status=SubmissionStatus.QUEUED,
            )
            SubmissionSource.objects.create(submission=submission, source_code=source_code)
            JudgeJob.objects.create(
                submission=submission,
                package=package,
                language=language,
                config=config,
            )

        cls._publish_event(
            SUBMISSION_STATUS,
            {"submission_id": submission.id, "status": submission.status},
            group=f"submission_{submission.id}",
        )
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
    def get_submission_by_share_token(cls, token: str) -> Submission | None:
        """Resolve a metadata-only share token."""

        try:
            parsed = uuid.UUID(token)
        except (ValueError, TypeError, AttributeError):
            return None
        return (
            Submission.objects.select_related("user", "problem", "language", "judged_on")
            .filter(share_token=parsed)
            .first()
        )

    @classmethod
    def get_user_submissions(cls, user: Any, problem: Any | None = None) -> QuerySet[Submission]:
        """Return scored submissions visible to the user, optionally by problem.

        Args:
            user: User requesting submissions.
            problem: Optional problem instance.

        Returns:
            Queryset of scored submissions ordered by recency.
        """
        queryset = Submission.objects.select_related("problem", "language", "judged_on").filter(
            mode=SubmissionMode.SUBMIT
        )
        if not getattr(user, "is_staff", False):
            queryset = queryset.filter(user=user)
        if problem is not None:
            queryset = queryset.filter(problem=problem)
        return queryset

    @staticmethod
    def _is_problem_maintainer(user: Any, submission: Submission) -> bool:
        if not getattr(user, "is_authenticated", False):
            return False
        return (
            submission.problem.authors.filter(pk=user.pk).exists()
            or submission.problem.curators.filter(pk=user.pk).exists()
        )

    @classmethod
    def can_view_submission(cls, user: Any, submission: Submission) -> bool:
        """Evaluate whether a user can view submission metadata."""

        if submission.is_public:
            return True
        if not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False) or submission.user_id == user.id:
            return True
        return cls._is_problem_maintainer(user, submission)

    @classmethod
    def can_view_submission_private(cls, user: Any, submission: Submission) -> bool:
        """Evaluate whether a user can see source, cases, and error detail."""

        if not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False) or submission.user_id == user.id:
            return True
        return cls._is_problem_maintainer(user, submission)

    @classmethod
    def can_edit_submission(cls, user: Any, submission: Submission) -> bool:
        """Evaluate whether a user may change public/share settings."""

        if not getattr(user, "is_authenticated", False):
            return False
        return getattr(user, "is_staff", False) or submission.user_id == user.id

    @classmethod
    def set_submission_public(cls, submission: Submission, is_public: bool) -> Submission:
        """Set public metadata visibility for a submission."""

        submission.is_public = is_public
        submission.save(update_fields=["is_public", "updated_at"])
        return submission

    @classmethod
    def create_share_token(cls, submission: Submission) -> Submission:
        """Issue a new metadata-only share token."""

        submission.share_token = uuid.uuid4()
        submission.save(update_fields=["share_token", "updated_at"])
        return submission

    @classmethod
    def revoke_share_token(cls, submission: Submission) -> Submission:
        """Revoke the current share token."""

        submission.share_token = None
        submission.save(update_fields=["share_token", "updated_at"])
        return submission

    @classmethod
    @transaction.atomic
    def rejudge_submission(cls, submission: Submission) -> None:
        """Reset a submission and queue its job for rejudging.

        Args:
            submission: Submission to reset and queue.
        """
        submission = Submission.objects.select_for_update().get(pk=submission.pk)
        job = JudgeJob.objects.select_for_update().filter(submission=submission).first()
        package = job.package if job is not None else submission.problem.packages.filter(is_active=True).first()
        if package is None and submission.mode != SubmissionMode.RUN:
            raise SubmissionError("No active test data package is available for this problem.")

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
        submission.judged_on = None
        submission.subtask_scores = {}
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
                "judged_on",
                "subtask_scores",
                "updated_at",
            ]
        )
        SubmissionTestCase.objects.filter(submission=submission).delete()

        if job is None:
            job = JudgeJob.objects.create(
                submission=submission,
                package=package,
                language=submission.language,
                config=cls._build_job_config(
                    problem=submission.problem,
                    language=submission.language,
                    package=package,
                    contest_participation=submission.contest_participation,
                    mode=submission.mode,
                    custom_input=submission.custom_input,
                ),
            )
        job.status = JudgeJobStatus.QUEUED
        job.attempts = 0
        job.claimed_by = None
        job.lease_expires_at = None
        job.claimed_at = None
        job.started_at = None
        job.finished_at = None
        job.last_error = ""
        job.config = cls._build_job_config(
            problem=submission.problem,
            language=submission.language,
            package=package,
            contest_participation=submission.contest_participation,
            mode=submission.mode,
            custom_input=submission.custom_input,
        )
        job.save(
            update_fields=[
                "status",
                "attempts",
                "claimed_by",
                "lease_expires_at",
                "claimed_at",
                "started_at",
                "finished_at",
                "last_error",
                "config",
                "updated_at",
            ]
        )

        cls._publish_event(
            SUBMISSION_STATUS,
            {"submission_id": submission.id, "status": SubmissionStatus.QUEUED},
            group=f"submission_{submission.id}",
        )

    @classmethod
    def rejudge_problem(cls, problem: Any) -> int:
        """Rejudge all submissions for a problem.

        Args:
            problem: Problem instance.

        Returns:
            Number of queued submissions.
        """
        submissions = list(Submission.objects.filter(problem=problem))
        for submission in submissions:
            cls.rejudge_submission(submission)
        return len(submissions)

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
    def _build_job_config(
        cls,
        *,
        problem: Any,
        language: Language,
        package: Any,
        contest_participation: Any | None,
        mode: str = SubmissionMode.SUBMIT,
        custom_input: str = "",
    ) -> dict[str, Any]:
        """Snapshot limits and scoring mode for one judge job."""

        manifest = (package.manifest if package is not None else {}) or {}
        config: dict[str, Any] = {
            "time_limit": problem.time_limit,
            "memory_limit": problem.memory_limit,
            "short_circuit": bool(manifest.get("short_circuit", problem.short_circuit)),
            "partial_score": bool(manifest.get("partial_score", problem.partial_score)),
            "mode": mode,
            "custom_input": custom_input,
        }

        from apps.problems.models import LanguageLimit

        language_limit = LanguageLimit.objects.filter(problem=problem, language=language).first()
        if language_limit is not None:
            config["time_limit"] = language_limit.time_limit
            config["memory_limit"] = language_limit.memory_limit

        if contest_participation is not None:
            contest_problem = contest_participation.contest.contest_problems.filter(problem=problem).first()
            if contest_problem is not None:
                config["contest_points"] = contest_problem.points
        return config

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

        allowed_relations = ["languages_allowed", "allowed_languages", "languages", "runtimes"]
        for relation in allowed_relations:
            manager = getattr(problem, relation, None)
            if manager is None or not hasattr(manager, "exists"):
                continue
            if manager.exists() and not manager.filter(id=language.id).exists():
                raise SubmissionError("Selected language is not allowed for this problem.")
            return

    @classmethod
    def _validate_problem_access(cls, *, user: Any, problem: Any) -> None:
        """Require problem visibility or an active contest participation."""

        if problem.is_accessible_by(user):
            return

        from apps.contests.constants import ParticipationStatus
        from apps.contests.models import ContestParticipation

        now = timezone.now()
        has_active_contest = ContestParticipation.objects.filter(
            user=user,
            status=ParticipationStatus.LIVE,
            contest__is_visible=True,
            contest__start_time__lte=now,
            contest__end_time__gt=now,
            contest__contest_problems__problem=problem,
        ).exists()
        if not has_active_contest:
            raise SubmissionError("You do not have access to this problem.")

    @classmethod
    def _check_run_rate_limit(cls, user: Any) -> None:
        """Enforce the separate per-user run rate limit."""

        if getattr(user, "is_staff", False):
            return

        limit = int(getattr(settings, "RUN_RATE_LIMIT_PER_MINUTE", 10))
        window_start = timezone.now() - timedelta(minutes=1)
        recent_count = Submission.objects.filter(
            user=user,
            mode=SubmissionMode.RUN,
            created_at__gte=window_start,
        ).count()
        if recent_count >= limit:
            raise SubmissionError("Run rate limit exceeded. Try again shortly.")

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
        recent_count = Submission.objects.filter(
            user=user,
            mode=SubmissionMode.SUBMIT,
            created_at__gte=window_start,
        ).count()
        if recent_count >= limit:
            raise SubmissionError("Submission rate limit exceeded. Try again shortly.")

    @classmethod
    def _publish_event(cls, event_type: str, payload: dict[str, Any], *, group: str | None = None) -> None:
        """Publish a domain event through the configured event bus.

        Args:
            event_type: Event type constant (e.g. ``SUBMISSION_CREATED``).
            payload: Event payload data.
            group: Optional explicit WebSocket group.
        """
        publish_sync(Event(type=event_type, payload=payload), group=group)

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
