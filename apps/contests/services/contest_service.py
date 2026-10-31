from __future__ import annotations

import hmac
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.contests.constants import ContestVisibility, ParticipationStatus
from apps.contests.models import Contest, ContestParticipation, ContestProblem
from core import events as core_events
from core.exceptions import ContestAccessDeniedError, ContestError

if TYPE_CHECKING:
    from datetime import datetime


class ContestService:
    """Service layer encapsulating contest management and access flows."""

    @staticmethod
    @transaction.atomic
    def create_contest(
        name: str,
        key: str,
        organizer: Any,
        start_time: datetime,
        end_time: datetime,
        **kwargs: Any,
    ) -> Contest:
        """Create and return a new contest.

        Args:
            name: Contest display name.
            key: Unique short contest key.
            organizer: User organizing contest.
            start_time: Contest start datetime.
            end_time: Contest end datetime.
            **kwargs: Extra contest fields.

        Returns:
            Created contest object.

        Raises:
            ContestError: If the schedule is invalid.
        """

        if end_time <= start_time:
            raise ContestError("Contest end time must be after start time.")

        contest = Contest.objects.create(
            name=name,
            key=key,
            start_time=start_time,
            end_time=end_time,
            **kwargs,
        )
        contest.organizers.add(organizer)
        return contest

    @staticmethod
    @transaction.atomic
    def update_contest(contest: Contest, **kwargs: Any) -> Contest:
        """Update mutable contest attributes.

        Args:
            contest: Contest to update.
            **kwargs: Field/value updates.

        Returns:
            Updated contest instance.

        Raises:
            ContestError: If resulting schedule is invalid.
        """

        new_start = kwargs.get("start_time", contest.start_time)
        new_end = kwargs.get("end_time", contest.end_time)
        if new_end <= new_start:
            raise ContestError("Contest end time must be after start time.")

        for field_name, value in kwargs.items():
            setattr(contest, field_name, value)
        contest.save()
        return contest

    @staticmethod
    @transaction.atomic
    def add_problem(
        contest: Contest,
        problem: Any,
        label: str,
        points: float,
        **kwargs: Any,
    ) -> ContestProblem:
        """Add a problem to a contest.

        Args:
            contest: Target contest.
            problem: Problem model instance.
            label: Problem label in the contest.
            points: Problem points.
            **kwargs: Additional ContestProblem fields.

        Returns:
            Created contest-problem mapping.
        """

        order = kwargs.pop("order", contest.contest_problems.count() + 1)
        return ContestProblem.objects.create(
            contest=contest,
            problem=problem,
            label=label,
            points=points,
            order=order,
            **kwargs,
        )

    @staticmethod
    @transaction.atomic
    def remove_problem(contest: Contest, problem: Any) -> None:
        """Remove a problem from a contest.

        Args:
            contest: Target contest.
            problem: Problem to remove.
        """

        ContestProblem.objects.filter(contest=contest, problem=problem).delete()

    @staticmethod
    @transaction.atomic
    def reorder_problems(contest: Contest, label_order: list[str]) -> None:
        """Reorder contest problems by provided label ordering.

        Args:
            contest: Target contest.
            label_order: Ordered list of labels.

        Raises:
            ContestError: If labels don't match existing set.
        """

        existing = {item.label for item in contest.contest_problems.all()}
        requested = set(label_order)
        if existing != requested:
            raise ContestError("Label set mismatch for reorder operation.")

        for idx, label in enumerate(label_order, start=1):
            ContestProblem.objects.filter(contest=contest, label=label).update(order=idx)

    @staticmethod
    def can_join_contest(
        user: Any,
        contest: Contest,
        access_code: str | None = None,
        *,
        allow_finished: bool = False,
    ) -> bool:
        """Return whether user may create a participation for contest."""

        if not getattr(user, "is_authenticated", False):
            return False
        if contest.banned_users.filter(pk=user.pk).exists():
            return False
        if contest.is_upcoming:
            return False
        if contest.is_finished and not allow_finished:
            return False
        if ContestService.is_contest_staff(user, contest):
            return True
        if contest.access_code and access_code and hmac.compare_digest(contest.access_code, access_code):
            return True
        if not contest.is_visible:
            return False
        if contest.visibility == ContestVisibility.PUBLIC:
            return True
        return ContestService.can_see_contest(user, contest)

    @staticmethod
    @transaction.atomic
    def join_contest(contest: Contest, user: Any, access_code: str | None = None) -> ContestParticipation:
        """Join a contest in live mode.

        Args:
            contest: Contest to join.
            user: User joining.
            access_code: Optional access code.

        Returns:
            Participation record.

        Raises:
            ContestAccessDeniedError: If access is denied or the contest is not joinable.
        """

        if not ContestService.can_join_contest(user, contest, access_code):
            raise ContestAccessDeniedError("You are not allowed to join this contest.")

        participation, created = ContestParticipation.objects.get_or_create(
            contest=contest,
            user=user,
            status=ParticipationStatus.LIVE,
            virtual_start=None,
            defaults={"format_data": {}},
        )

        if created:
            core_events.publish_sync(
                core_events.Event(
                    type=core_events.CONTEST_PARTICIPATION_JOINED,
                    payload={"contest_id": contest.id, "user_id": user.id, "participation_id": participation.id},
                )
            )
        return participation

    @staticmethod
    @transaction.atomic
    def start_virtual(contest: Contest, user: Any, access_code: str | None = None) -> ContestParticipation:
        """Start virtual participation for a user.

        Args:
            contest: Target contest.
            user: User starting virtual participation.
            access_code: Optional contest access code.

        Returns:
            Virtual participation record.

        Raises:
            ContestError: If virtual participation is not supported.
            ContestAccessDeniedError: If the user may not enter the contest.
        """

        if not contest.time_limit:
            raise ContestError("Virtual participation requires contest.time_limit.")
        if not ContestService.can_join_contest(user, contest, access_code, allow_finished=True):
            raise ContestAccessDeniedError("You are not allowed to enter this contest.")

        existing = (
            ContestParticipation.objects.filter(
                contest=contest,
                user=user,
                status=ParticipationStatus.VIRTUAL,
            )
            .order_by("id")
            .first()
        )
        if existing is not None:
            return existing

        return ContestParticipation.objects.create(
            contest=contest,
            user=user,
            status=ParticipationStatus.VIRTUAL,
            virtual_start=timezone.now(),
            format_data={},
        )

    @staticmethod
    @transaction.atomic
    def submit_to_contest(
        *,
        user: Any,
        contest: Contest,
        problem_code: str,
        language: Any,
        source_code: str,
    ) -> Any:
        """Create a submission bound to the caller's contest participation."""

        participation = (
            contest.participations.select_for_update()
            .filter(
                user=user,
                is_disqualified=False,
                status__in=[ParticipationStatus.LIVE, ParticipationStatus.VIRTUAL],
            )
            .first()
        )
        if participation is None:
            raise ContestAccessDeniedError("Join the contest before submitting.")

        if participation.status == ParticipationStatus.LIVE and not contest.is_active:
            raise ContestError("Contest is not active.")
        if participation.status == ParticipationStatus.VIRTUAL and participation.time_remaining <= timedelta(0):
            raise ContestError("Virtual participation time has expired.")

        contest_problem = (
            ContestProblem.objects.select_for_update()
            .select_related("problem")
            .filter(contest=contest, problem__code=problem_code)
            .first()
        )
        if contest_problem is None:
            raise ContestError("Problem is not part of this contest.")

        if contest_problem.max_submissions is not None:
            used = participation.submissions.filter(problem=contest_problem.problem).count()
            if used >= contest_problem.max_submissions:
                raise ContestError("Submission limit reached for this problem.")

        from apps.submissions.services import SubmissionService

        return SubmissionService.create_submission(
            user=user,
            problem=contest_problem.problem,
            language=language,
            source_code=source_code,
            contest_participation=participation,
        )

    @staticmethod
    @transaction.atomic
    def disqualify_user(contest: Contest, user: Any) -> None:
        """Disqualify all participations of a user in a contest."""

        ContestParticipation.objects.filter(contest=contest, user=user).update(is_disqualified=True)

    @staticmethod
    @transaction.atomic
    def undisqualify_user(contest: Contest, user: Any) -> None:
        """Undo disqualification for all participations of a user in a contest."""

        ContestParticipation.objects.filter(contest=contest, user=user).update(is_disqualified=False)

    @staticmethod
    def get_visible_contests(user: Any) -> QuerySet[Contest]:
        """Return contests visible to a given user.

        Args:
            user: Requesting user.

        Returns:
            Queryset of visible contests.
        """

        base = Contest.objects.filter(is_visible=True)

        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return base.distinct()

        if not getattr(user, "is_authenticated", False):
            return base.filter(visibility=ContestVisibility.PUBLIC).distinct()

        user_org_ids: list[int] = []
        if hasattr(user, "organizations"):
            user_org_ids = list(user.organizations.values_list("id", flat=True))

        return (
            base.filter(
                Q(visibility=ContestVisibility.PUBLIC)
                | Q(organizers=user)
                | Q(curators=user)
                | Q(testers=user)
                | Q(visibility=ContestVisibility.ORGANIZATION, organizations__id__in=user_org_ids)
            )
            .distinct()
            .prefetch_related("organizations")
        )

    @staticmethod
    def can_see_contest(user: Any, contest: Contest) -> bool:
        """Return whether user has access to view a contest."""

        if not contest.is_visible:
            return ContestService.is_contest_staff(user, contest)

        if contest.visibility == ContestVisibility.PUBLIC:
            return True

        if not getattr(user, "is_authenticated", False):
            return False

        if ContestService.is_contest_staff(user, contest):
            return True

        if contest.visibility == ContestVisibility.PRIVATE:
            return contest.participations.filter(user=user).exists()

        if contest.visibility == ContestVisibility.ORGANIZATION:
            user_org_manager = getattr(user, "organizations", None)
            if user_org_manager is None:
                return False
            return contest.organizations.filter(id__in=user_org_manager.values_list("id", flat=True)).exists()

        return False

    @staticmethod
    def is_contest_staff(user: Any, contest: Contest) -> bool:
        """Return whether user can administrate a contest.

        Staff includes organizers, curators, and platform staff.
        """

        if not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True
        return contest.organizers.filter(pk=user.pk).exists() or contest.curators.filter(pk=user.pk).exists()
