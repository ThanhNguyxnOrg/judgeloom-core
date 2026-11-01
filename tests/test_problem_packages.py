from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.problems.services.package_service import PackageImportService
from core.exceptions import ValidationError


def make_zip(entries: dict[str, bytes], name: str = "package.zip") -> SimpleUploadedFile:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path, data in entries.items():
            zf.writestr(path, data)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")


@pytest.mark.django_db
class TestPackageImportService:
    def test_import_zip_creates_active_package(self, problem):
        upload = make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"})
        payload = upload.read()
        upload.seek(0)

        package = PackageImportService.import_zip(problem, upload)

        assert package.problem_id == problem.id
        assert package.sha256 == hashlib.sha256(payload).hexdigest()
        assert package.size_bytes == len(payload)
        assert package.is_active is True
        assert package.version == 1
        assert package.test_cases.count() == 1

    def test_import_zip_creates_hashed_cases_and_points(self, problem):
        upload = make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"})

        package = PackageImportService.import_zip(problem, upload)
        case = package.test_cases.get()

        assert case.order == 1
        assert case.input_file == "data/01.in"
        assert case.output_file == "data/01.ans"
        assert case.input_sha256 == hashlib.sha256(b"1 2\n").hexdigest()
        assert case.output_sha256 == hashlib.sha256(b"3\n").hexdigest()
        assert case.points == 100.0
        assert case.group == "default"
        assert package.manifest["cases"][0]["points"] == 100.0

    def test_import_zip_with_manifest_preserves_points_and_groups(self, problem):
        manifest = {
            "schema": 1,
            "cases": [
                {
                    "id": "01",
                    "input": "data/01.in",
                    "answer": "data/01.ans",
                    "points": 30,
                    "group": "g1",
                }
            ],
            "groups": [{"id": "g1", "points": 30, "mode": "sum"}],
        }
        upload = make_zip(
            {
                "manifest.json": json.dumps(manifest).encode(),
                "data/01.in": b"1 2\n",
                "data/01.ans": b"3\n",
            }
        )

        package = PackageImportService.import_zip(problem, upload)
        case = package.test_cases.get()

        assert case.points == 30.0
        assert case.group == "g1"
        assert package.manifest["groups"] == manifest["groups"]

    def test_import_zip_rejects_missing_output(self, problem):
        upload = make_zip({"data/01.in": b"1 2\n"})

        with pytest.raises(ValidationError, match="matching"):
            PackageImportService.import_zip(problem, upload)

    def test_import_zip_rejects_path_traversal(self, problem):
        upload = make_zip({"../evil.in": b"1", "../evil.ans": b"1"})

        with pytest.raises(ValidationError, match="Invalid file path"):
            PackageImportService.import_zip(problem, upload)

    def test_import_zip_rejects_too_many_cases(self, problem):
        entries: dict[str, bytes] = {}
        for index in range(201):
            entries[f"data/{index:03d}.in"] = b"1"
            entries[f"data/{index:03d}.ans"] = b"1"

        with pytest.raises(ValidationError, match="maximum allowed test cases"):
            PackageImportService.import_zip(problem, make_zip(entries))

    def test_import_zip_rejects_duplicate_case_stems(self, problem):
        upload = make_zip(
            {
                "group_a/case1.in": b"1",
                "group_a/case1.out": b"1",
                "group_b/case1.in": b"2",
                "group_b/case1.out": b"2",
            }
        )

        with pytest.raises(ValidationError, match="Duplicate testcase stem"):
            PackageImportService.import_zip(problem, upload)

    def test_import_zip_rejects_non_zip(self, problem):
        upload = SimpleUploadedFile("tests.rar", b"not a zip")

        with pytest.raises(ValidationError, match="ZIP archive"):
            PackageImportService.import_zip(problem, upload)

    def test_import_zip_rejects_bad_zip(self, problem):
        upload = SimpleUploadedFile("tests.zip", b"not a zip")

        with pytest.raises(ValidationError, match="Invalid ZIP archive"):
            PackageImportService.import_zip(problem, upload)

    def test_activate_deactivates_previous_package(self, problem):
        first = PackageImportService.import_zip(
            problem,
            make_zip({"data/01.in": b"1", "data/01.ans": b"1"}),
        )
        second = PackageImportService.import_zip(
            problem,
            make_zip({"data/02.in": b"2", "data/02.ans": b"2"}),
        )

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.is_active is False
        assert second.is_active is True
        assert second.version == 2

    def test_import_zip_rejects_unknown_case_group(self, problem):
        manifest = {
            "cases": [
                {
                    "input": "data/01.in",
                    "answer": "data/01.ans",
                    "points": 50,
                    "group": "missing",
                }
            ],
            "groups": [{"id": "default", "points": 100, "mode": "sum"}],
        }
        upload = make_zip(
            {
                "manifest.json": json.dumps(manifest).encode(),
                "data/01.in": b"1 2\n",
                "data/01.ans": b"3\n",
            }
        )

        with pytest.raises(ValidationError, match="unknown groups"):
            PackageImportService.import_zip(problem, upload)

    def test_import_zip_accepts_inline_testlib_validator(self, problem):
        manifest = {
            "validator": {"type": "testlib", "source": "int main() { return 0; }"},
            "cases": [{"input": "data/01.in", "answer": "data/01.ans"}],
        }
        upload = make_zip(
            {
                "manifest.json": json.dumps(manifest).encode(),
                "data/01.in": b"1 2\n",
                "data/01.ans": b"3\n",
            }
        )

        package = PackageImportService.import_zip(problem, upload)
        assert package.manifest["validator"]["type"] == "testlib"

    def test_import_zip_rejects_unknown_validator_type(self, problem):
        manifest = {
            "validator": {"type": "python"},
            "cases": [{"input": "data/01.in", "answer": "data/01.ans"}],
        }
        upload = make_zip(
            {
                "manifest.json": json.dumps(manifest).encode(),
                "data/01.in": b"1 2\n",
                "data/01.ans": b"3\n",
            }
        )

        with pytest.raises(ValidationError, match="validator type"):
            PackageImportService.import_zip(problem, upload)

    def test_import_zip_rejects_testlib_validator_without_source(self, problem):
        manifest = {
            "validator": {"type": "testlib"},
            "cases": [{"input": "data/01.in", "answer": "data/01.ans"}],
        }
        upload = make_zip(
            {
                "manifest.json": json.dumps(manifest).encode(),
                "data/01.in": b"1 2\n",
                "data/01.ans": b"3\n",
            }
        )

        with pytest.raises(ValidationError, match="requires inline source"):
            PackageImportService.import_zip(problem, upload)

    def test_import_zip_rejects_non_numeric_points(self, problem):
        manifest = {
            "cases": [
                {
                    "input": "data/01.in",
                    "answer": "data/01.ans",
                    "points": "not-a-number",
                    "group": "default",
                }
            ],
            "groups": [{"id": "default", "points": 100, "mode": "sum"}],
        }
        upload = make_zip(
            {
                "manifest.json": json.dumps(manifest).encode(),
                "data/01.in": b"1 2\n",
                "data/01.ans": b"3\n",
            }
        )

        with pytest.raises(ValidationError, match="points must be numeric"):
            PackageImportService.import_zip(problem, upload)

    def test_activate_existing_package_deactivates_others(self, problem):
        first = PackageImportService.import_zip(
            problem,
            make_zip({"data/01.in": b"1", "data/01.ans": b"1"}),
        )
        second = PackageImportService.import_zip(
            problem,
            make_zip({"data/02.in": b"2", "data/02.ans": b"2"}),
        )

        PackageImportService.activate(first)
        first.refresh_from_db()
        second.refresh_from_db()

        assert first.is_active is True
        assert second.is_active is False


@pytest.mark.django_db
def test_problem_types_reads_active_package_interactive_flag(problem):
    manifest = {"checker": {"type": "interactive"}, "cases": []}
    upload = make_zip(
        {
            "manifest.json": json.dumps(manifest).encode(),
            "data/01.in": b"1",
            "data/01.ans": b"1",
        }
    )
    PackageImportService.import_zip(problem, upload)

    assert "interactive" in problem.types
