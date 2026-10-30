from __future__ import annotations

import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.judge.models import JudgeJob, JudgeJobStatus
from apps.problems.services.package_service import PackageImportService
from apps.submissions.constants import SubmissionStatus
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
