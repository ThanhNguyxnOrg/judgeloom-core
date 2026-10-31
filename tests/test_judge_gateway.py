from __future__ import annotations

import hashlib
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import Client
from django.utils import timezone

from apps.judge.models import JudgeJob, JudgeJobStatus
from apps.judge.services.judge_gateway_service import JudgeGatewayService
from apps.problems.services.package_service import PackageImportService
from apps.submissions.constants import SubmissionResult, SubmissionStatus
from apps.submissions.models import SubmissionTestCase
from apps.submissions.services import SubmissionService
from tests.factories import JudgeFactory


def auth_header(token: str = "secret") -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.mark.django_db
class TestJudgeTokenAuth:
    def test_heartbeat_accepts_valid_token_and_updates_judge(self):
        judge = JudgeFactory(
            name="gateway-heartbeat",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
            online=False,
        )
        client = Client()

        response = client.post(
            "/api/v1/judge/heartbeat",
            data=json.dumps({"load": 0.25, "running_jobs": 1}),
            content_type="application/json",
            **auth_header(),
        )

        assert response.status_code == 200
        judge.refresh_from_db()
        assert judge.last_seen is not None
        assert judge.online is True
        assert judge.current_load == 0.25
        assert judge.load == 0.25

    def test_heartbeat_rejects_wrong_token(self):
        JudgeFactory(name="gateway-wrong-token", token_hash=hashlib.sha256(b"secret").hexdigest())
        client = Client()

        response = client.post(
            "/api/v1/judge/heartbeat",
            data=json.dumps({"load": 0.1}),
            content_type="application/json",
            **auth_header("wrong"),
        )

        assert response.status_code == 401

    def test_heartbeat_rejects_blocked_judge(self):
        JudgeFactory(
            name="gateway-blocked",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
            is_blocked=True,
        )
        client = Client()

        response = client.post(
            "/api/v1/judge/heartbeat",
            data=json.dumps({"load": 0.1}),
            content_type="application/json",
            **auth_header(),
        )

        assert response.status_code == 403

    def test_register_persists_protocol_and_capabilities(self):
        judge = JudgeFactory(
            name="gateway-register",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
            online=False,
        )
        client = Client()

        response = client.post(
            "/api/v1/judge/register",
            data=json.dumps(
                {
                    "protocol_version": 1,
                    "capabilities": {"languages": ["PY3"], "sandbox": "go-judge"},
                }
            ),
            content_type="application/json",
            **auth_header(),
        )

        assert response.status_code == 200
        judge.refresh_from_db()
        assert judge.protocol_version == 1
        assert judge.capabilities == {"languages": ["PY3"], "sandbox": "go-judge"}
        assert judge.online is True
        assert judge.last_seen is not None


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


def make_submission(user, problem, language):
    import_package(problem)
    return SubmissionService.create_submission(
        user=user,
        problem=problem,
        language=language,
        source_code="print(1)",
    )


@pytest.mark.django_db
class TestClaimJob:
    def test_claim_returns_queued_job_and_sets_lease(self, user, problem, language):
        first = make_submission(user, problem, language)
        second = make_submission(user, problem, language)
        judge = JudgeFactory()
        job_ids = set(JudgeJob.objects.filter(submission__in=[first, second]).values_list("id", flat=True))

        claimed = JudgeGatewayService.claim_job(judge, ["PY3"])

        assert claimed is not None
        assert claimed.pk in job_ids
        claimed.refresh_from_db()
        assert claimed.status == JudgeJobStatus.CLAIMED
        assert claimed.claimed_by_id == judge.id
        assert claimed.attempts == 1
        assert claimed.lease_expires_at is not None

    def test_second_claim_returns_a_different_job(self, user, problem, language):
        make_submission(user, problem, language)
        make_submission(user, problem, language)
        judge = JudgeFactory()

        first = JudgeGatewayService.claim_job(judge, ["PY3"])
        second = JudgeGatewayService.claim_job(judge, ["PY3"])

        assert first is not None
        assert second is not None
        assert first.pk != second.pk

    def test_claim_without_matching_language_returns_none(self, user, problem, language):
        submission = make_submission(user, problem, language)
        judge = JudgeFactory()

        claimed = JudgeGatewayService.claim_job(judge, ["CPP17"])

        assert claimed is None
        job = JudgeJob.objects.get(submission=submission)
        assert job.status == JudgeJobStatus.QUEUED

    def test_claim_route_returns_204_when_no_job(self):
        JudgeFactory(
            name="gateway-empty",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
        )
        client = Client()

        response = client.post(
            "/api/v1/judge/jobs/claim",
            data=json.dumps({"languages": ["PY3"]}),
            content_type="application/json",
            **auth_header(),
        )

        assert response.status_code == 204
        assert JudgeJob.objects.count() == 0

    def test_claim_route_rejects_blocked_judge(self):
        JudgeFactory(
            name="gateway-claim-blocked",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
            is_blocked=True,
        )
        client = Client()

        response = client.post(
            "/api/v1/judge/jobs/claim",
            data=json.dumps({"languages": ["PY3"]}),
            content_type="application/json",
            **auth_header(),
        )

        assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
class TestLeaseExpiry:
    def test_expired_lease_is_requeued_and_claimable(self, user, problem, language):
        submission = make_submission(user, problem, language)
        judge_a = JudgeFactory(name="lease-judge-a")
        judge_b = JudgeFactory(name="lease-judge-b")
        job = JudgeJob.objects.get(submission=submission)
        job.status = JudgeJobStatus.CLAIMED
        job.claimed_by = judge_a
        job.attempts = 1
        job.lease_expires_at = timezone.now() - timedelta(seconds=1)
        job.save()

        claimed = JudgeGatewayService.claim_job(judge_b, ["PY3"])

        assert claimed is not None
        assert claimed.pk == job.pk
        claimed.refresh_from_db()
        assert claimed.claimed_by_id == judge_b.id
        assert claimed.attempts == 2

    def test_max_attempts_marks_job_failed_and_submission_ie(self, user, problem, language):
        submission = make_submission(user, problem, language)
        judge = JudgeFactory(name="lease-exhausted")
        job = JudgeJob.objects.get(submission=submission)
        job.status = JudgeJobStatus.CLAIMED
        job.claimed_by = judge
        job.attempts = job.max_attempts
        job.lease_expires_at = timezone.now() - timedelta(seconds=1)
        job.save()

        expired = JudgeGatewayService.expire_stale_jobs()

        assert expired == 1
        job.refresh_from_db()
        submission.refresh_from_db()
        assert job.status == JudgeJobStatus.FAILED
        assert submission.status == SubmissionStatus.ERROR
        assert submission.result == SubmissionResult.IE

    def test_concurrent_claims_only_one_wins_on_postgres(self, user, problem, language):
        if connection.vendor != "postgresql":
            pytest.skip("row locking behavior requires PostgreSQL")
        make_submission(user, problem, language)
        judges = [JudgeFactory(name="race-judge-a"), JudgeFactory(name="race-judge-b")]

        def claim(judge):
            close_old_connections()
            try:
                return JudgeGatewayService.claim_job(judge, ["PY3"])
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, judges))

        assert sum(result is not None for result in results) == 1


def make_result_judge(name: str = "result-judge"):
    return JudgeFactory(
        name=name,
        token_hash=hashlib.sha256(b"secret").hexdigest(),
        online=True,
    )


def post_json(path: str, payload: dict, token: str = "secret"):
    return Client().post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        **auth_header(token),
    )


@pytest.mark.django_db
class TestResultRoutes:
    def test_start_marks_job_running(self, user, problem, language):
        submission = make_submission(user, problem, language)
        judge = make_result_judge()
        job = JudgeGatewayService.claim_job(judge, ["PY3"])

        response = post_json(f"/api/v1/judge/jobs/{job.pk}/start", {})

        assert response.status_code == 200
        job.refresh_from_db()
        submission.refresh_from_db()
        assert job.status == JudgeJobStatus.RUNNING
        assert submission.status == SubmissionStatus.JUDGING

    def test_cases_are_idempotent(self, user, problem, language):
        submission = make_submission(user, problem, language)
        judge = make_result_judge("result-idempotent")
        job = JudgeGatewayService.claim_job(judge, ["PY3"])
        case = {
            "case_number": 1,
            "status": SubmissionResult.AC,
            "time_used": 0.1,
            "memory_used": 1024,
            "points": 100,
            "total_points": 100,
        }

        first = post_json(f"/api/v1/judge/jobs/{job.pk}/cases", {"cases": [case]})
        second = post_json(f"/api/v1/judge/jobs/{job.pk}/cases", {"cases": [case]})

        assert first.status_code == 200
        assert second.status_code == 200
        assert SubmissionTestCase.objects.filter(submission=submission).count() == 1
        submission.refresh_from_db()
        assert submission.case_total == 1
        assert submission.case_passed == 1
        assert submission.current_testcase == 1

    def test_finish_uses_server_score_and_ignores_worker_points(self, user, problem, language):
        submission = make_submission(user, problem, language)
        judge = make_result_judge("result-finish")
        job = JudgeGatewayService.claim_job(judge, ["PY3"])
        post_json(f"/api/v1/judge/jobs/{job.pk}/start", {})
        post_json(
            f"/api/v1/judge/jobs/{job.pk}/cases",
            {
                "cases": [
                    {
                        "case_number": 1,
                        "status": SubmissionResult.AC,
                        "time_used": 0.1,
                        "memory_used": 1024,
                        "points": 100,
                        "total_points": 100,
                    }
                ]
            },
        )

        response = post_json(
            f"/api/v1/judge/jobs/{job.pk}/finish",
            {"points": 1000, "time_used": 99, "memory_used": 999999},
        )

        assert response.status_code == 200
        submission.refresh_from_db()
        job.refresh_from_db()
        assert submission.status == SubmissionStatus.COMPLETED
        assert submission.result == SubmissionResult.AC
        assert submission.points == 100.0
        assert submission.time_used == 0.1
        assert submission.memory_used == 1024
        assert job.status == JudgeJobStatus.SUCCEEDED

    def test_duplicate_finish_is_idempotent(self, user, problem, language):
        submission = make_submission(user, problem, language)
        judge = make_result_judge("result-duplicate-finish")
        job = JudgeGatewayService.claim_job(judge, ["PY3"])
        post_json(
            f"/api/v1/judge/jobs/{job.pk}/cases",
            {
                "cases": [
                    {
                        "case_number": 1,
                        "status": SubmissionResult.AC,
                        "points": 100,
                        "total_points": 100,
                    }
                ]
            },
        )

        first = post_json(f"/api/v1/judge/jobs/{job.pk}/finish", {})
        second = post_json(f"/api/v1/judge/jobs/{job.pk}/finish", {})

        assert first.status_code == 200
        assert second.status_code == 200
        submission.refresh_from_db()
        assert submission.points == 100.0
        assert SubmissionTestCase.objects.filter(submission=submission).count() == 1

    def test_wrong_judge_cannot_update_job(self, user, problem, language):
        make_submission(user, problem, language)
        judge_a = make_result_judge("result-owner")
        JudgeFactory(
            name="result-other",
            token_hash=hashlib.sha256(b"other-secret").hexdigest(),
            online=True,
        )
        job = JudgeGatewayService.claim_job(judge_a, ["PY3"])

        response = post_json(
            f"/api/v1/judge/jobs/{job.pk}/cases",
            {"cases": [{"case_number": 1, "status": SubmissionResult.AC, "points": 100, "total_points": 100}]},
            token="other-secret",
        )

        assert response.status_code == 403

    def test_fail_sets_compile_error(self, user, problem, language):
        submission = make_submission(user, problem, language)
        judge = make_result_judge("result-fail")
        job = JudgeGatewayService.claim_job(judge, ["PY3"])

        response = post_json(
            f"/api/v1/judge/jobs/{job.pk}/fail",
            {"status": "error", "result": SubmissionResult.CE, "error_message": "bad compile"},
        )

        assert response.status_code == 200
        submission.refresh_from_db()
        assert submission.status == SubmissionStatus.ERROR
        assert submission.result == SubmissionResult.CE
        assert submission.error_message == "bad compile"


@pytest.mark.django_db
class TestPackageDownload:
    def test_download_package_by_hash(self, problem):
        upload = make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"})
        payload = upload.read()
        upload.seek(0)
        package = PackageImportService.import_zip(problem, upload)
        JudgeFactory(
            name="download-judge",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
        )
        client = Client()

        response = client.get(
            f"/api/v1/judge/packages/{problem.pk}?sha256={package.sha256}",
            **auth_header(),
        )

        assert response.status_code == 200
        assert b"".join(response.streaming_content) == payload
        response.close()

    def test_download_wrong_hash_returns_404(self, problem):
        PackageImportService.import_zip(
            problem,
            make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"}),
        )
        JudgeFactory(
            name="download-wrong-hash",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
        )
        client = Client()

        response = client.get(
            f"/api/v1/judge/packages/{problem.pk}?sha256={'0' * 64}",
            **auth_header(),
        )

        assert response.status_code == 404

    def test_download_rejects_blocked_judge(self, problem):
        package = PackageImportService.import_zip(
            problem,
            make_zip({"data/01.in": b"1 2\n", "data/01.ans": b"3\n"}),
        )
        JudgeFactory(
            name="download-blocked",
            token_hash=hashlib.sha256(b"secret").hexdigest(),
            is_blocked=True,
        )
        client = Client()

        response = client.get(
            f"/api/v1/judge/packages/{problem.pk}?sha256={package.sha256}",
            **auth_header(),
        )

        assert response.status_code == 403
