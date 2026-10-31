from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db.models import Min
from django.utils import timezone
from ninja import Router

from apps.judge.api.schemas import JudgeDetailOut, JudgeMetricsOut, JudgeOut, LanguageOut
from apps.judge.models import Judge, JudgeJob, JudgeJobStatus
from apps.judge.services import JudgeService
from core.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from django.http import HttpRequest

router = Router(tags=["judge"])


def _require_staff(request: HttpRequest) -> None:
    """Require staff-level access for an endpoint.

    Args:
        request: Incoming Ninja request.

    Raises:
        PermissionDeniedError: If request user is not staff.
    """
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise PermissionDeniedError("Authentication required.")
    if not getattr(user, "is_staff", False):
        raise PermissionDeniedError("Staff access required.")


def _require_superuser(request: HttpRequest) -> None:
    """Require superuser access for an endpoint.

    Args:
        request: Incoming Ninja request.

    Raises:
        PermissionDeniedError: If request user is not a superuser.
    """
    _require_staff(request)
    if not getattr(request.user, "is_superuser", False):
        raise PermissionDeniedError("Superuser access required.")


@router.get("/judges", response=list[JudgeOut])
def list_judges(request: HttpRequest) -> list[JudgeOut]:
    """List all judges for staff users.

    Args:
        request: Incoming Ninja request.

    Returns:
        List of judge summary payloads.
    """
    _require_staff(request)

    judges = JudgeService.list_judges()
    return [
        JudgeOut(
            name=judge.name,
            online=judge.online,
            is_blocked=judge.is_blocked,
            status=judge.status,
            ping=judge.ping,
            load=judge.load,
        )
        for judge in judges
    ]


@router.get("/judges/{name}", response=JudgeDetailOut)
def judge_detail(request: HttpRequest, name: str) -> JudgeDetailOut:
    """Get detailed information for a judge.

    Args:
        request: Incoming Ninja request.
        name: Judge identifier.

    Returns:
        Judge detail payload.
    """
    _require_staff(request)

    judge = JudgeService.get_judge(name)
    uptime = judge.uptime
    return JudgeDetailOut(
        name=judge.name,
        online=judge.online,
        is_blocked=judge.is_blocked,
        status=judge.status,
        ping=judge.ping,
        load=judge.load,
        hostname=judge.hostname,
        description=judge.description,
        last_ip=judge.last_ip,
        start_time=judge.start_time,
        uptime_seconds=int(uptime.total_seconds()) if uptime else None,
        languages=list(judge.runtimes.values_list("key", flat=True)),
        problems=list(judge.problems.values_list("code", flat=True)),
        capabilities=judge.capabilities or {},
    )


@router.get("/metrics", response=JudgeMetricsOut)
def judge_metrics(request: HttpRequest) -> JudgeMetricsOut:
    """Return aggregate queue and judge health metrics for staff."""

    _require_staff(request)
    now = timezone.now()
    queued = JudgeJob.objects.filter(status=JudgeJobStatus.QUEUED)
    claimed = JudgeJob.objects.filter(status=JudgeJobStatus.CLAIMED)
    running = JudgeJob.objects.filter(status=JudgeJobStatus.RUNNING)
    oldest = queued.aggregate(oldest=Min("created_at"))["oldest"]

    return JudgeMetricsOut(
        queued=queued.count(),
        claimed=claimed.count(),
        running=running.count(),
        failed_last_24h=JudgeJob.objects.filter(
            status=JudgeJobStatus.FAILED,
            finished_at__gte=now - timedelta(hours=24),
        ).count(),
        online_judges=Judge.objects.filter(online=True, is_blocked=False).count(),
        blocked_judges=Judge.objects.filter(is_blocked=True).count(),
        oldest_queued_seconds=max(0, int((now - oldest).total_seconds())) if oldest else 0,
        leases_expiring_60s=JudgeJob.objects.filter(
            status__in=[JudgeJobStatus.CLAIMED, JudgeJobStatus.RUNNING],
            lease_expires_at__gt=now,
            lease_expires_at__lte=now + timedelta(seconds=60),
        ).count(),
    )


@router.get("/languages", response=list[LanguageOut])
def list_languages(request: HttpRequest) -> list[LanguageOut]:
    """List enabled programming languages.

    Args:
        request: Incoming Ninja request.

    Returns:
        List of language payloads.
    """
    _ = request
    languages = JudgeService.get_supported_languages()
    return [
        LanguageOut(
            id=language.id,
            key=language.key,
            name=language.name,
            short_name=language.short_name,
            ace_mode=language.ace_mode,
            pygments_name=language.pygments_name,
            description=language.description,
            extension=language.extension,
            is_enabled=language.is_enabled,
        )
        for language in languages
    ]


@router.get("/languages/{key}", response=LanguageOut)
def language_detail(request: HttpRequest, key: str) -> LanguageOut:
    """Get details for one language key.

    Args:
        request: Incoming Ninja request.
        key: Language key.

    Returns:
        Language payload.
    """
    _ = request
    language = JudgeService.get_language_by_key(key)
    return LanguageOut(
        id=language.id,
        key=language.key,
        name=language.name,
        short_name=language.short_name,
        ace_mode=language.ace_mode,
        pygments_name=language.pygments_name,
        description=language.description,
        extension=language.extension,
        is_enabled=language.is_enabled,
    )


@router.post("/judges/{name}/block", response=dict[str, str])
def block_judge(request: HttpRequest, name: str) -> dict[str, str]:
    """Block a judge from receiving new submissions.

    Args:
        request: Incoming Ninja request.
        name: Judge identifier.

    Returns:
        Simple status response.
    """
    _require_superuser(request)

    judge = JudgeService.get_judge(name)
    JudgeService.block_judge(judge)
    return {"name": judge.name, "status": "blocked"}


@router.post("/judges/{name}/unblock", response=dict[str, str])
def unblock_judge(request: HttpRequest, name: str) -> dict[str, str]:
    """Unblock a judge and restore dispatch eligibility.

    Args:
        request: Incoming Ninja request.
        name: Judge identifier.

    Returns:
        Simple status response.
    """
    _require_superuser(request)

    judge = JudgeService.get_judge(name)
    JudgeService.unblock_judge(judge)
    return {"name": judge.name, "status": "unblocked"}
