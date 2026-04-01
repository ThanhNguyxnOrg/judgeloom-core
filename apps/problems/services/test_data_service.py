from __future__ import annotations

import zipfile
from collections import defaultdict
from typing import Any

from django.db import transaction
from django.db.models import QuerySet

from apps.problems.models import Problem, ProblemTestCase, ProblemTestData
from core.exceptions import ValidationError


class TestDataService:
    """Service methods for managing problem test data."""

    @staticmethod
    @transaction.atomic
    def upload_test_data(problem: Problem, archive_file: Any) -> ProblemTestData:
        """Create or update archived test data for a problem and parse its contents.

        Args:
            problem: Problem to update.
            archive_file: Uploaded ZIP archive file containing .in and .out/.ans pairs.

        Returns:
            ProblemTestData: Persisted test data object.

        Raises:
            ValidationError: If the archive is invalid or has mismatched testcases.
        """
        if not archive_file.name.endswith(".zip"):
            raise ValidationError("Test data must be a ZIP archive.")

        try:
            with zipfile.ZipFile(archive_file, "r") as zf:
                file_list = zf.namelist()
        except zipfile.BadZipFile as exc:
            raise ValidationError("Invalid ZIP archive.") from exc

        import pathlib

        # Match inputs (.in) and outputs (.out or .ans)
        pairs: dict[str, dict[str, str]] = defaultdict(dict)
        for filename in file_list:
            if filename.endswith("/") or filename.startswith("__MACOSX"):
                continue

            path_obj = pathlib.Path(filename)

            # Security: Prevent path traversal
            if ".." in path_obj.parts or path_obj.is_absolute():
                raise ValidationError(f"Invalid file path in archive: {filename}")

            name = path_obj.name
            stem = path_obj.stem
            ext = path_obj.suffix.lower()

            if ext == ".in":
                if "in" in pairs[stem]:
                    raise ValidationError(f"Duplicate testcase stem detected: {stem}")
                pairs[stem]["in"] = filename
            elif ext in (".out", ".ans"):
                if "out" in pairs[stem]:
                    raise ValidationError(f"Duplicate testcase stem detected: {stem}")
                pairs[stem]["out"] = filename

        valid_cases = []
        for base, parts in pairs.items():
            if "in" in parts and "out" in parts:
                # Try to extract integer from base name for natural ordering
                try:
                    order = int("".join(filter(str.isdigit, base)) or "0")
                except ValueError:
                    order = 0
                valid_cases.append((order, base, parts["in"], parts["out"]))

        if not valid_cases:
            raise ValidationError("Archive must contain matching .in and .out/.ans files.")

        # Security: Prevent Zip Bomb / DB Exhaustion
        MAX_TEST_CASES = 200
        if len(valid_cases) > MAX_TEST_CASES:
            raise ValidationError(f"Archive exceeds maximum allowed test cases ({MAX_TEST_CASES}).")

        valid_cases.sort(key=lambda x: (x[0], x[1]))

        # Update or create the ProblemTestData record
        test_data, _ = ProblemTestData.objects.get_or_create(problem=problem)
        test_data.zipfile = archive_file
        test_data.save(update_fields=["zipfile", "updated_at"])

        # Clear old cases
        ProblemTestCase.objects.filter(problem_data=test_data).delete()

        # Insert new cases
        cases_to_create = []
        for index, (_, _, in_file, out_file) in enumerate(valid_cases, start=1):
            cases_to_create.append(
                ProblemTestCase(
                    problem_data=test_data,
                    order=index,
                    input_file=in_file,
                    output_file=out_file,
                    points=0.0,
                    is_pretest=False,
                )
            )

        ProblemTestCase.objects.bulk_create(cases_to_create)

        # Distribute points evenly if problem has total points
        if problem.points > 0 and len(cases_to_create) > 0:
            avg_points = round(problem.points / len(cases_to_create), 2)
            ProblemTestCase.objects.filter(problem_data=test_data).update(points=avg_points)

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
