from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Q, QuerySet

from apps.problems.constants import ProblemVisibility, SolutionVerdict
from apps.problems.models import Problem, Solution
from core.events import PROBLEM_CREATED, PROBLEM_UPDATED, Event, publish_sync
from core.exceptions import NotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterable


class ProblemService:
    """Domain service for creating, updating, and querying problems."""

    @staticmethod
    @transaction.atomic
    def create_problem(code: str, name: str, author: Any, **kwargs: Any) -> Problem:
        """Create a new problem and assign ownership relations.

        Args:
            code: Unique problem code.
            name: Human-readable problem title.
            author: User creating the problem.
            **kwargs: Additional problem fields and relation collections.

        Returns:
            Problem: Persisted problem instance.
        """

        authors: Iterable[Any] = kwargs.pop("authors", [])
        curators: Iterable[Any] = kwargs.pop("curators", [])
        testers: Iterable[Any] = kwargs.pop("testers", [])
        organizations: Iterable[Any] = kwargs.pop("organizations", [])
        languages_allowed: Iterable[Any] = kwargs.pop("languages_allowed", [])

        problem = Problem.objects.create(code=code, name=name, **kwargs)
        problem.authors.add(author)
        if authors:
            problem.authors.add(*authors)
        if curators:
            problem.curators.add(*curators)
        if testers:
            problem.testers.add(*testers)
        if organizations:
            problem.organizations.add(*organizations)
        if languages_allowed:
            problem.languages_allowed.add(*languages_allowed)

        publish_sync(Event(type=PROBLEM_CREATED, payload={"problem_id": problem.pk, "code": problem.code}))
        return problem

    @staticmethod
    @transaction.atomic
    def update_problem(problem: Problem, **kwargs: Any) -> Problem:
        """Update mutable fields for an existing problem.

        Args:
            problem: Problem instance to update.
            **kwargs: Field updates.

        Returns:
            Problem: Updated problem instance.
        """

        for field, value in kwargs.items():
            setattr(problem, field, value)
        problem.save(update_fields=[*kwargs.keys(), "updated_at"])
        publish_sync(Event(type=PROBLEM_UPDATED, payload={"problem_id": problem.pk, "code": problem.code}))
        return problem

    @staticmethod
    def get_visible_problems(user: Any) -> QuerySet[Problem]:
        """Return problems visible to a given user.

        Args:
            user: User requesting the list.

        Returns:
            QuerySet[Problem]: Visibility-filtered queryset.
        """

        base_queryset = Problem.objects.select_related("license").prefetch_related(
            "authors",
            "curators",
            "organizations",
            "tags",
        )

        visibility_filter = Q(visibility=ProblemVisibility.PUBLIC) | Q(visibility=ProblemVisibility.UNLISTED)

        if not getattr(user, "is_authenticated", False):
            return base_queryset.filter(visibility_filter).distinct()

        user_filter = Q(authors=user) | Q(curators=user) | Q(testers=user)
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return base_queryset.distinct()

        return base_queryset.filter(visibility_filter | user_filter).distinct()

    @staticmethod
    def get_problem_by_code(code: str) -> Problem:
        """Load a problem by canonical code.

        Args:
            code: Problem code.

        Raises:
            NotFoundError: If no matching problem exists.

        Returns:
            Problem: Found problem instance.
        """

        problem = Problem.objects.filter(code=code).first()
        if problem is None:
            raise NotFoundError(f"Problem '{code}' does not exist.")
        return problem

    @staticmethod
    def can_see_problem(user: Any, problem: Problem) -> bool:
        """Check whether a user can read the problem."""

        return problem.is_accessible_by(user)

    @staticmethod
    def can_edit_problem(user: Any, problem: Problem) -> bool:
        """Check whether a user can edit the problem."""

        if not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True
        return problem.authors.filter(pk=user.pk).exists() or problem.curators.filter(pk=user.pk).exists()

    @staticmethod
    def get_problem_statistics(problem: Problem) -> dict[str, float | int | str]:
        """Compute aggregate statistics for a problem.

        Args:
            problem: Target problem.

        Returns:
            dict[str, float | int | str]: Submission and solution health metrics.
        """

        solution_qs = Solution.objects.filter(problem=problem)
        total_solutions = solution_qs.count()
        total_public_solutions = solution_qs.filter(is_public=True).count()
        total_correct = solution_qs.filter(verdict=SolutionVerdict.CORRECT).count()
        total_partial = solution_qs.filter(verdict=SolutionVerdict.PARTIAL).count()
        total_wrong = solution_qs.filter(verdict=SolutionVerdict.WRONG).count()

        accepted_rate = (total_correct / total_solutions * 100.0) if total_solutions else 0.0

        return {
            "problem_code": problem.code,
            "total_submissions": total_solutions,
            "total_public_solutions": total_public_solutions,
            "total_accepted": total_correct,
            "total_partial": total_partial,
            "total_wrong": total_wrong,
            "accepted_rate": round(accepted_rate, 2),
        }
