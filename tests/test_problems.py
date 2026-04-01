"""
JudgeLoom — Problem Tests
============================

Unit tests for Problem model properties and accessibility logic.
"""

from __future__ import annotations

import pytest

from apps.problems.constants import ProblemVisibility
from tests.factories import ProblemFactory, UserFactory


@pytest.mark.django_db
class TestProblemModel:
    """Tests for the Problem model."""

    def test_create_problem(self, problem):
        """Factory creates a valid public problem."""
        assert problem.pk is not None
        assert problem.visibility == ProblemVisibility.PUBLIC

    def test_problem_str(self, problem):
        """__str__ returns 'code - name' format."""
        assert problem.code in str(problem)
        assert problem.name in str(problem)

    def test_is_public(self, problem):
        """Public visibility returns True for is_public."""
        assert problem.is_public is True

    def test_is_not_public(self):
        """Private visibility returns False for is_public."""
        problem = ProblemFactory(code="private1", visibility=ProblemVisibility.PRIVATE)
        assert problem.is_public is False

    def test_accessible_by_staff(self, problem):
        """Staff users can access private problems."""
        problem.visibility = ProblemVisibility.PRIVATE
        problem.save()

        staff = UserFactory(username="staff_access", is_staff=True)
        assert problem.is_accessible_by(staff) is True

    def test_accessible_by_anonymous(self, problem):
        """Public problems are accessible by anonymous users."""
        from django.contrib.auth.models import AnonymousUser

        assert problem.is_accessible_by(AnonymousUser()) is True

    def test_types_includes_standard(self, problem):
        """Default problem includes standard type."""
        assert "standard" in problem.types


@pytest.mark.django_db
class TestTestDataService:
    """Tests for the TestDataService and zip pipeline."""

    def test_upload_test_data_valid_zip(self, problem):
        """Service correctly parses and persists valid zip files."""
        import zipfile
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.problems.services.test_data_service import TestDataService

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("case1.in", b"1 2")
            zf.writestr("case1.out", b"3")
            zf.writestr("case2.in", b"3 4")
            zf.writestr("case2.ans", b"7")
            zf.writestr("ignore.txt", b"ignore")
            zf.writestr("__MACOSX/case3.in", b"ignore")

        zip_buffer.seek(0)
        archive_file = SimpleUploadedFile("tests.zip", zip_buffer.read(), content_type="application/zip")

        test_data = TestDataService.upload_test_data(problem, archive_file)

        # Verify persistence
        assert test_data.problem == problem

        cases = TestDataService.get_test_cases(problem)
        assert cases.count() == 2

        assert cases[0].order == 1
        assert cases[0].input_file == "case1.in"
        assert cases[0].output_file == "case1.out"
        assert cases[0].points == 50.0  # ProblemFactory default points = 100.0

        assert cases[1].order == 2
        assert cases[1].input_file == "case2.in"
        assert cases[1].output_file == "case2.ans"
        assert cases[1].points == 50.0

    def test_upload_test_data_invalid_extension(self, problem):
        """Reject non-zip files."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.problems.services.test_data_service import TestDataService
        from core.exceptions import ValidationError

        archive_file = SimpleUploadedFile("tests.rar", b"invalid")
        with pytest.raises(ValidationError, match="must be a ZIP archive"):
            TestDataService.upload_test_data(problem, archive_file)

    def test_upload_test_data_bad_zip(self, problem):
        """Reject corrupt zip files."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.problems.services.test_data_service import TestDataService
        from core.exceptions import ValidationError

        archive_file = SimpleUploadedFile("tests.zip", b"not a zip file")
        with pytest.raises(ValidationError, match="Invalid ZIP archive"):
            TestDataService.upload_test_data(problem, archive_file)

    def test_upload_test_data_no_matching_cases(self, problem):
        """Reject zips without matching in/out pairs."""
        import zipfile
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.problems.services.test_data_service import TestDataService
        from core.exceptions import ValidationError

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("case1.in", b"1 2")
            zf.writestr("case2.out", b"3")

        zip_buffer.seek(0)
        archive_file = SimpleUploadedFile("tests.zip", zip_buffer.read(), content_type="application/zip")

        with pytest.raises(ValidationError, match="Archive must contain matching"):
            TestDataService.upload_test_data(problem, archive_file)

    def test_upload_test_data_rejects_path_traversal(self, problem):
        """Reject zip entries containing traversal paths."""
        import zipfile
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.problems.services.test_data_service import TestDataService
        from core.exceptions import ValidationError

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("../../evil.in", b"1")
            zf.writestr("../../evil.out", b"1")

        zip_buffer.seek(0)
        archive_file = SimpleUploadedFile("tests.zip", zip_buffer.read(), content_type="application/zip")

        with pytest.raises(ValidationError, match="Invalid file path"):
            TestDataService.upload_test_data(problem, archive_file)

    def test_upload_test_data_rejects_too_many_cases(self, problem):
        """Reject zip archives exceeding test case limit."""
        import zipfile
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.problems.services.test_data_service import TestDataService
        from core.exceptions import ValidationError

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i in range(201):
                zf.writestr(f"case{i}.in", b"1")
                zf.writestr(f"case{i}.out", b"1")

        zip_buffer.seek(0)
        archive_file = SimpleUploadedFile("tests.zip", zip_buffer.read(), content_type="application/zip")

        with pytest.raises(ValidationError, match="exceeds maximum allowed test cases"):
            TestDataService.upload_test_data(problem, archive_file)

    def test_upload_test_data_rejects_duplicate_case_stems(self, problem):
        """Reject archives containing duplicate case stems across directories."""
        import zipfile
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.problems.services.test_data_service import TestDataService
        from core.exceptions import ValidationError

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("group_a/case1.in", b"1")
            zf.writestr("group_a/case1.out", b"1")
            zf.writestr("group_b/case1.in", b"2")
            zf.writestr("group_b/case1.out", b"2")

        zip_buffer.seek(0)
        archive_file = SimpleUploadedFile("tests.zip", zip_buffer.read(), content_type="application/zip")

        with pytest.raises(ValidationError, match="Duplicate testcase stem"):
            TestDataService.upload_test_data(problem, archive_file)
