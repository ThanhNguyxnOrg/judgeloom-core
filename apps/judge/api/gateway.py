from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.http import HttpResponse
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
from apps.judge.models import Judge, JudgeJob
from apps.judge.services.judge_gateway_service import JudgeGatewayService
from apps.judge.services.judge_result_service import JudgeResultService

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
    cases = [case.model_dump() for case in payload.cases]
    JudgeResultService.record_cases(_get_job(job_id), judge, cases)
    return {"ok": True, "received": len(cases)}


@router.post("/jobs/{job_id}/finish", auth=JudgeTokenAuth())
def finish_job(request: HttpRequest, job_id: int, payload: JudgeFinishIn) -> Any:
    """Finalize a job with server-computed scores."""

    judge = _request_judge(request)
    submission = JudgeResultService.finish(_get_job(job_id), judge, payload.model_dump())
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
    submission = JudgeResultService.fail(_get_job(job_id), judge, payload.model_dump())
    return {
        "submission_id": submission.pk,
        "status": submission.status,
        "result": submission.result,
        "error_message": submission.error_message,
    }
