from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.judge.models import JudgeJobStatus
from apps.problems.services.package_service import PackageImportService
from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.services import SubmissionService
from tests.factories import JudgeFactory


def make_zip(entries: dict[str, bytes], name: str = "package.zip") -> SimpleUploadedFile:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path, data in entries.items():
            zf.writestr(path, data)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")


def import_two_case_package(problem):
    manifest = {
        "cases": [
            {"input": "data/01.in", "answer": "data/01.ans", "points": 50, "group": "default"},
            {"input": "data/02.in", "answer": "data/02.ans", "points": 50, "group": "default"},
        ],
        "groups": [{"id": "default", "points": 100, "mode": "sum"}],
    }
    entries: dict[str, bytes] = {"manifest.json": json.dumps(manifest).encode()}
    for case in manifest["cases"]:
        entries[case["input"]] = b"1 2\n"
        entries[case["answer"]] = b"3\n"
    return PackageImportService.import_zip(problem, make_zip(entries))


class FakeJudge:
    def __init__(self, token: str = "secret") -> None:
        self.client = Client()
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def post(self, path: str, payload: dict):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            **self.headers,
        )


@pytest.mark.django_db
def test_fake_worker_end_to_end(user, problem, language):
    import_two_case_package(problem)
    JudgeFactory(
        name="e2e-judge",
        token_hash=hashlib.sha256(b"secret").hexdigest(),
        online=True,
    )
    submission = SubmissionService.create_submission(
        user=user,
        problem=problem,
        language=language,
        source_code="print(1)",
    )
    assert submission.judge_job.status == JudgeJobStatus.QUEUED

    worker = FakeJudge()
    claim = worker.post("/api/v1/judge/jobs/claim", {"languages": ["PY3"]})
    assert claim.status_code == 200
    claim_payload = claim.json()
    job_id = claim_payload["job_id"]
    package_sha256 = claim_payload["package"]["sha256"]

    assert worker.post(f"/api/v1/judge/jobs/{job_id}/start", {}).status_code == 200
    cases = worker.post(
        f"/api/v1/judge/jobs/{job_id}/cases",
        {
            "package_sha256": package_sha256,
            "cases": [
                {
                    "case_number": 1,
                    "status": SubmissionResult.AC,
                    "time_used": 0.05,
                    "memory_used": 1024,
                    "points": 50,
                    "total_points": 50,
                },
                {
                    "case_number": 2,
                    "status": SubmissionResult.WA,
                    "time_used": 0.07,
                    "memory_used": 2048,
                    "points": 0,
                    "total_points": 50,
                },
            ]
        },
    )
    assert cases.status_code == 200

    finish = worker.post(
        f"/api/v1/judge/jobs/{job_id}/finish",
        {"package_sha256": package_sha256, "points": 1000},
    )
    assert finish.status_code == 200

    submission.refresh_from_db()
    assert submission.status == SubmissionStatus.COMPLETED
    assert submission.result == SubmissionResult.WA
    assert submission.points == 0.0
    assert submission.case_total == 2
    assert submission.case_passed == 1
    assert submission.test_cases.count() == 2
    assert set(submission.test_cases.values_list("status", flat=True)) == {
        SubmissionResult.AC,
        SubmissionResult.WA,
    }

    duplicate = worker.post(
        f"/api/v1/judge/jobs/{job_id}/finish",
        {"package_sha256": package_sha256, "points": 1000},
    )
    assert duplicate.status_code == 200
    submission.refresh_from_db()
    assert submission.test_cases.count() == 2
    assert submission.points == 0.0
