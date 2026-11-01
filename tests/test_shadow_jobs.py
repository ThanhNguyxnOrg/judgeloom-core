from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.judge.models import ShadowJob
from apps.problems.services.package_service import PackageImportService
from apps.submissions.services import SubmissionService
from tests.factories import JudgeFactory


def make_zip(entries: dict[str, bytes], name: str = "package.zip") -> SimpleUploadedFile:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path, data in entries.items():
            zf.writestr(path, data)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")


@pytest.mark.django_db
class TestShadowJobs:
    def test_staff_can_replay_without_touching_primary_submission(self, user, admin_user, problem, language):
        package = PackageImportService.import_zip(
            problem,
            make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"}),
        )
        submission = SubmissionService.create_submission(
            user=user,
            problem=problem,
            language=language,
            source_code="print(1)",
        )

        staff = Client()
        staff.force_login(admin_user)
        created = staff.post(
            f"/api/submissions/{submission.id}/shadow",
            data="{}",
            content_type="application/json",
        )
        assert created.status_code == 200
        shadow_id = created.json()["id"]

        judge = JudgeFactory(
            name="shadow-judge",
            token_hash=hashlib.sha256(b"shadow-secret").hexdigest(),
        )
        headers = {"HTTP_AUTHORIZATION": "Bearer shadow-secret"}
        worker = Client()
        claimed = worker.post(
            "/api/v1/judge/shadow/jobs/claim",
            data=json.dumps({"languages": [language.key], "max_jobs": 1}),
            content_type="application/json",
            **headers,
        )
        assert claimed.status_code == 200
        payload = claimed.json()
        assert payload["job_id"] == shadow_id
        assert payload["package"]["sha256"] == package.sha256

        job_id = payload["job_id"]
        assert worker.post(f"/api/v1/judge/shadow/jobs/{job_id}/start", **headers).status_code == 200
        cases = worker.post(
            f"/api/v1/judge/shadow/jobs/{job_id}/cases",
            data=json.dumps(
                {
                    "package_sha256": package.sha256,
                    "cases": [{"case_number": 1, "status": "AC", "points": 100, "total_points": 100}],
                }
            ),
            content_type="application/json",
            **headers,
        )
        assert cases.status_code == 200
        finished = worker.post(
            f"/api/v1/judge/shadow/jobs/{job_id}/finish",
            data=json.dumps({"package_sha256": package.sha256, "status": "completed"}),
            content_type="application/json",
            **headers,
        )
        assert finished.status_code == 200
        assert finished.json()["result"] == "AC"

        submission.refresh_from_db()
        shadow = ShadowJob.objects.get(pk=shadow_id)
        assert submission.status == "Q"
        assert submission.result is None
        assert shadow.status == "succeeded"
        assert shadow.claimed_by_id == judge.id
        assert shadow.result == "AC"
        assert len(shadow.case_results) == 1

        listed = staff.get(f"/api/submissions/{submission.id}/shadows")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == shadow_id

    def test_non_staff_cannot_create_replay(self, user, problem, language):
        package = PackageImportService.import_zip(
            problem,
            make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"}),
        )
        submission = SubmissionService.create_submission(
            user=user,
            problem=problem,
            language=language,
            source_code="print(1)",
        )
        client = Client()
        client.force_login(user)

        response = client.post(
            f"/api/submissions/{submission.id}/shadow",
            data="{}",
            content_type="application/json",
        )

        assert response.status_code == 403
        assert ShadowJob.objects.filter(submission=submission).count() == 0
        assert package.is_active is True
