from __future__ import annotations

import json
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.judge.models import JudgeJob, JudgeJobStatus
from apps.judge.services.scoring_service import ScoringService
from apps.problems.services.package_service import PackageImportService
from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.models import SubmissionTestCase
from apps.submissions.services import SubmissionService
from core.exceptions import SubmissionError
from tests.factories import JudgeFactory


def make_zip(entries: dict[str, bytes], name: str = "package.zip") -> SimpleUploadedFile:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path, data in entries.items():
            zf.writestr(path, data)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")


def import_package(problem):
    return PackageImportService.import_zip(
        problem,
        make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"}),
    )


def import_package_with_manifest(problem, manifest):
    entries: dict[str, bytes] = {"manifest.json": json.dumps(manifest).encode()}
    for case in manifest["cases"]:
        entries[case["input"]] = b"1 2\n"
        entries[case["answer"]] = b"3\n"
    return PackageImportService.import_zip(problem, make_zip(entries))


@pytest.mark.django_db
class TestSubmissionJobCreation:
    def test_create_submission_creates_queued_job_with_active_package(self, user, problem, language):
        package = import_package(problem)

        submission = SubmissionService.create_submission(
            user=user,
            problem=problem,
            language=language,
            source_code="print(1)",
        )

        job = submission.judge_job
        assert isinstance(job, JudgeJob)
        assert job.status == JudgeJobStatus.QUEUED
        assert job.package_id == package.id
        assert job.language_id == language.id
        assert job.attempts == 0
        assert job.max_attempts == 3

    def test_create_submission_without_active_package_raises(self, user, problem, language):
        with pytest.raises(SubmissionError, match="package"):
            SubmissionService.create_submission(
                user=user,
                problem=problem,
                language=language,
                source_code="print(1)",
            )

    def test_rejudge_resets_job_and_deletes_test_cases(self, user, problem, language):
        import_package(problem)
        submission = SubmissionService.create_submission(
            user=user,
            problem=problem,
            language=language,
            source_code="print(1)",
        )
        judge = JudgeFactory()
        job = submission.judge_job
        job.status = JudgeJobStatus.CLAIMED
        job.claimed_by = judge
        job.attempts = 1
        job.lease_expires_at = timezone.now()
        job.save()
        SubmissionTestCase.objects.create(
            submission=submission,
            case_number=1,
            status="AC",
            points=100,
            total_points=100,
        )

        SubmissionService.rejudge_submission(submission)

        submission.refresh_from_db()
        job.refresh_from_db()
        assert submission.status == SubmissionStatus.QUEUED
        assert submission.test_cases.count() == 0
        assert job.status == JudgeJobStatus.QUEUED
        assert job.attempts == 0
        assert job.claimed_by is None
        assert job.lease_expires_at is None


@pytest.mark.django_db
class TestScoringService:
    def test_all_ac_cases_score_full_points(self, problem):
        package = import_package(problem)

        summary = ScoringService.score(
            package,
            [
                {
                    "case_number": 1,
                    "status": SubmissionResult.AC,
                    "points": 100,
                    "total_points": 100,
                }
            ],
        )

        assert summary.result == SubmissionResult.AC
        assert summary.status == SubmissionStatus.COMPLETED
        assert summary.points == 100.0
        assert summary.case_total == 1
        assert summary.case_passed == 1

    def test_wa_case_scores_zero(self, problem):
        package = import_package(problem)

        summary = ScoringService.score(
            package,
            [
                {
                    "case_number": 1,
                    "status": SubmissionResult.WA,
                    "points": 0,
                    "total_points": 100,
                }
            ],
        )

        assert summary.result == SubmissionResult.WA
        assert summary.points == 0.0

    def test_group_scores_are_capped_by_group_points(self, problem):
        manifest = {
            "cases": [
                {"input": "data/01.in", "answer": "data/01.ans", "points": 25, "group": "sum_group"},
                {"input": "data/02.in", "answer": "data/02.ans", "points": 25, "group": "sum_group"},
                {"input": "data/03.in", "answer": "data/03.ans", "points": 50, "group": "min_group"},
            ],
            "groups": [
                {"id": "sum_group", "points": 40, "mode": "sum"},
                {"id": "min_group", "points": 50, "mode": "min"},
            ],
        }
        package = import_package_with_manifest(problem, manifest)

        summary = ScoringService.score(
            package,
            [
                {"case_number": 1, "status": SubmissionResult.AC, "points": 25, "total_points": 25},
                {"case_number": 2, "status": SubmissionResult.AC, "points": 25, "total_points": 25},
                {"case_number": 3, "status": SubmissionResult.AC, "points": 50, "total_points": 50},
            ],
        )

        assert summary.subtask_scores["sum_group"] == 40.0
        assert summary.subtask_scores["min_group"] == 50.0
        assert summary.points == 90.0

    def test_partial_credit_yields_pt(self, problem):
        problem.partial_score = True
        problem.save(update_fields=["partial_score"])
        manifest = {
            "cases": [
                {"input": "data/01.in", "answer": "data/01.ans", "points": 50, "group": "g"},
                {"input": "data/02.in", "answer": "data/02.ans", "points": 50, "group": "g"},
            ],
            "groups": [{"id": "g", "points": 100, "mode": "sum"}],
        }
        package = import_package_with_manifest(problem, manifest)

        summary = ScoringService.score(
            package,
            [
                {"case_number": 1, "status": SubmissionResult.AC, "points": 50, "total_points": 50},
                {"case_number": 2, "status": SubmissionResult.WA, "points": 0, "total_points": 50},
            ],
        )

        assert summary.points == 50.0
        assert summary.result == SubmissionResult.PARTIAL

    def test_compile_error_sets_error_status(self, problem):
        package = import_package(problem)

        summary = ScoringService.score(
            package,
            [{"case_number": 1, "status": SubmissionResult.CE, "points": 0, "total_points": 100}],
        )

        assert summary.result == SubmissionResult.CE
        assert summary.status == SubmissionStatus.ERROR
        assert summary.points == 0.0
