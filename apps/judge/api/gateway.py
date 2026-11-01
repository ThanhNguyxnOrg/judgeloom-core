from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.http import FileResponse, HttpResponse
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from apps.judge.api.gateway_schemas import (
    JudgeCasesIn,
    JudgeClaimIn,
    JudgeFailIn,
    JudgeFinishIn,
    JudgeHeartbeatIn,
    JudgeHeartbeatOut,
    JudgeRegisterIn,
    JudgeRegisterOut,
)
from apps.judge.auth import JudgeTokenAuth
from apps.judge.models import Judge, JudgeJob, JudgeJobStatus, ShadowJob
from apps.judge.services.judge_gateway_service import LEASE_SECONDS, JudgeGatewayService
from apps.judge.services.judge_result_service import JudgeResultService
from apps.judge.services.shadow_job_service import ShadowJobService
from apps.problems.models import ProblemPackage
from core.exceptions import JudgeJobConflictError

if TYPE_CHECKING:
    from django.http import HttpRequest

router = Router(tags=["judge-gateway"])

HEARTBEAT_INTERVAL_SECONDS = 10


def _request_judge(request: HttpRequest) -> Judge:
    judge = getattr(request, "auth", None)
    if not isinstance(judge, Judge):
        raise HttpError(401, "Judge authentication required.")
    return judge


def _get_job(job_id: int) -> JudgeJob:
    job = JudgeJob.objects.filter(pk=job_id).first()
    if job is None:
        raise HttpError(404, "Judge job not found.")
    return job


def _verify_package(job: JudgeJob, package_sha256: str | None) -> None:
    if not package_sha256:
        return
    if job.package is None or package_sha256 != job.package.sha256:
        raise JudgeJobConflictError("The worker reported a stale package hash.")


def _get_shadow_job(job_id: int) -> ShadowJob:
    job = ShadowJob.objects.filter(pk=job_id).first()
    if job is None:
        raise HttpError(404, "Shadow job not found.")
    return job


def _verify_shadow_package(job: ShadowJob, package_sha256: str | None) -> None:
    if not package_sha256:
        return
    if job.package is None or package_sha256 != job.package.sha256:
        raise JudgeJobConflictError("The worker reported a stale package hash.")


@router.post("/register", response=JudgeRegisterOut, auth=JudgeTokenAuth())
def register(request: HttpRequest, payload: JudgeRegisterIn) -> JudgeRegisterOut:
    """Register or update a worker's protocol version and capabilities."""

    judge = _request_judge(request)
    now = timezone.now()
    judge.protocol_version = payload.protocol_version
    judge.capabilities = payload.capabilities
    judge.online = True
    judge.last_seen = now
    if judge.start_time is None:
        judge.start_time = now
    judge.save(
        update_fields=[
            "protocol_version",
            "capabilities",
            "online",
            "last_seen",
            "start_time",
            "updated_at",
        ]
    )
    return JudgeRegisterOut(judge_id=judge.pk, heartbeat_interval=HEARTBEAT_INTERVAL_SECONDS)


@router.post("/heartbeat", response=JudgeHeartbeatOut, auth=JudgeTokenAuth())
def heartbeat(request: HttpRequest, payload: JudgeHeartbeatIn) -> JudgeHeartbeatOut:
    """Record a worker heartbeat and current load."""

    judge = _request_judge(request)
    judge.online = True
    judge.last_seen = timezone.now()
    judge.current_load = payload.load
    judge.load = payload.load
    judge.save(
        update_fields=[
            "online",
            "last_seen",
            "current_load",
            "load",
            "updated_at",
        ]
    )
    JudgeJob.objects.filter(
        claimed_by=judge,
        status__in=[JudgeJobStatus.CLAIMED, JudgeJobStatus.RUNNING],
    ).update(lease_expires_at=timezone.now() + timedelta(seconds=LEASE_SECONDS))
    return JudgeHeartbeatOut(ok=True, next_heartbeat=HEARTBEAT_INTERVAL_SECONDS)


@router.post("/jobs/claim", auth=JudgeTokenAuth())
def claim_job(request: HttpRequest, payload: JudgeClaimIn) -> Any:
    """Claim one queued job for the authenticated worker."""

    judge = _request_judge(request)
    job = JudgeGatewayService.claim_job(judge, payload.languages, payload.max_jobs)
    if job is None:
        return HttpResponse(status=204)
    return JudgeGatewayService.claim_payload(job)


@router.post("/jobs/{job_id}/start", auth=JudgeTokenAuth())
def start_job(request: HttpRequest, job_id: int) -> Any:
    """Mark a claimed job as running."""

    judge = _request_judge(request)
    JudgeResultService.start(_get_job(job_id), judge)
    return {"ok": True}


@router.post("/jobs/{job_id}/cases", auth=JudgeTokenAuth())
def record_cases(request: HttpRequest, job_id: int, payload: JudgeCasesIn) -> Any:
    """Record a batch of per-case results."""

    judge = _request_judge(request)
    job = _get_job(job_id)
    _verify_package(job, payload.package_sha256)
    cases = [case.model_dump() for case in payload.cases]
    JudgeResultService.record_cases(job, judge, cases)
    return {"ok": True, "received": len(cases)}


@router.post("/jobs/{job_id}/finish", auth=JudgeTokenAuth())
def finish_job(request: HttpRequest, job_id: int, payload: JudgeFinishIn) -> Any:
    """Finalize a job with server-computed scores."""

    judge = _request_judge(request)
    job = _get_job(job_id)
    _verify_package(job, payload.package_sha256)
    submission = JudgeResultService.finish(job, judge, payload.model_dump())
    return {
        "submission_id": submission.pk,
        "status": submission.status,
        "result": submission.result,
        "points": submission.points,
        "case_total": submission.case_total,
        "case_passed": submission.case_passed,
    }


@router.post("/jobs/{job_id}/fail", auth=JudgeTokenAuth())
def fail_job(request: HttpRequest, job_id: int, payload: JudgeFailIn) -> Any:
    """Finalize a job as a compile/internal error."""

    judge = _request_judge(request)
    job = _get_job(job_id)
    _verify_package(job, payload.package_sha256)
    submission = JudgeResultService.fail(job, judge, payload.model_dump())
    return {
        "submission_id": submission.pk,
        "status": submission.status,
        "result": submission.result,
        "error_message": submission.error_message,
    }


@router.post("/shadow/jobs/claim", auth=JudgeTokenAuth())
def claim_shadow_job(request: HttpRequest, payload: JudgeClaimIn) -> Any:
    """Claim one queued shadow job for the authenticated worker."""

    judge = _request_judge(request)
    job = ShadowJobService.claim_job(judge, payload.languages)
    if job is None:
        return HttpResponse(status=204)
    return ShadowJobService.claim_payload(job)


@router.post("/shadow/jobs/{job_id}/start", auth=JudgeTokenAuth())
def start_shadow_job(request: HttpRequest, job_id: int) -> Any:
    judge = _request_judge(request)
    ShadowJobService.start(_get_shadow_job(job_id), judge)
    return {"ok": True}


@router.post("/shadow/jobs/{job_id}/cases", auth=JudgeTokenAuth())
def record_shadow_cases(request: HttpRequest, job_id: int, payload: JudgeCasesIn) -> Any:
    judge = _request_judge(request)
    job = _get_shadow_job(job_id)
    _verify_shadow_package(job, payload.package_sha256)
    ShadowJobService.record_cases(job, judge, [case.model_dump() for case in payload.cases])
    return {"ok": True, "received": len(payload.cases)}


@router.post("/shadow/jobs/{job_id}/finish", auth=JudgeTokenAuth())
def finish_shadow_job(request: HttpRequest, job_id: int, payload: JudgeFinishIn) -> Any:
    judge = _request_judge(request)
    job = _get_shadow_job(job_id)
    _verify_shadow_package(job, payload.package_sha256)
    job = ShadowJobService.finish(job, judge, payload.model_dump())
    return {
        "shadow_job_id": job.pk,
        "status": job.status,
        "result": job.result,
        "case_total": job.case_total,
        "case_passed": job.case_passed,
    }


@router.post("/shadow/jobs/{job_id}/fail", auth=JudgeTokenAuth())
def fail_shadow_job(request: HttpRequest, job_id: int, payload: JudgeFailIn) -> Any:
    judge = _request_judge(request)
    job = _get_shadow_job(job_id)
    _verify_shadow_package(job, payload.package_sha256)
    job = ShadowJobService.fail(job, judge, payload.model_dump())
    return {
        "shadow_job_id": job.pk,
        "status": job.status,
        "result": job.result,
        "error_message": job.error_message,
    }


@router.get("/packages/{problem_id}", auth=JudgeTokenAuth())
def download_package(request: HttpRequest, problem_id: int, sha256: str) -> Any:
    """Download an immutable package archive by problem and content hash."""

    _ = request
    package = ProblemPackage.objects.select_related("problem").filter(problem_id=problem_id, sha256=sha256).first()
    if package is None:
        raise HttpError(404, "Problem package not found.")
    return FileResponse(
        package.archive.open("rb"),
        as_attachment=True,
        filename=f"{package.problem.code}-{package.sha256}.zip",
    )
