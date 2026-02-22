from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import QuerySet

from apps.problems.models import Problem, ProblemTestCase, ProblemTestData

class TestDataService:
    """Service methods for managing problem test data."""

    @staticmethod
    @transaction.atomic
    def upload_test_data(problem: Problem, zipfile: Any) -> ProblemTestData:
        """Create or update archived test data for a problem.

        Args:
            problem: Problem to update.
            zipfile: Uploaded archive file.

        Returns:
            ProblemTestData: Persisted test data object.
        """

        test_data, _ = ProblemTestData.objects.get_or_create(problem=problem)
        test_data.zipfile = zipfile
        test_data.save(update_fields=["zipfile", "updated_at"])
        return test_data

    @staticmethod
    def get_test_cases(problem: Problem) -> QuerySet[ProblemTestCase]:
        """Fetch ordered test cases for a problem."""

        return ProblemTestCase.objects.filter(problem_data__problem=problem).select_related(
            "problem_data",
            "problem_data__problem",
        )

    @staticmethod
    @transaction.atomic
    def update_test_case(test_case: ProblemTestCase, **kwargs: Any) -> ProblemTestCase:
        """Update mutable testcase fields.

        Args:
            test_case: Test case to mutate.
            **kwargs: Updated values.

        Returns:
            ProblemTestCase: Updated testcase.
        """

        for field, value in kwargs.items():
            setattr(test_case, field, value)
        test_case.save(update_fields=[*kwargs.keys(), "updated_at"])
        return test_case
