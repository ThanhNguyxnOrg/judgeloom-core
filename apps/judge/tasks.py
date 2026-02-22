from __future__ import annotations

from celery import shared_task

from apps.judge.services.judge_maintenance_service import JudgeMaintenanceService


@shared_task(
    bind=True,
    name="judge.monitor_judges",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def monitor_judges(self: object) -> int:
    """Check judge heartbeats and mark stale judges offline.

    Args:
        self: Celery task instance.

    Returns:
        Number of judges that were marked offline.
    """

    return JudgeMaintenanceService.monitor_judges()


@shared_task(
    bind=True,
    name="judge.cleanup_stale_sessions",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def cleanup_stale_sessions(self: object) -> int:
    """Requeue stale judge sessions for in-flight submissions.

    Args:
        self: Celery task instance.

    Returns:
        Number of submissions requeued.
    """

    return JudgeMaintenanceService.cleanup_stale_sessions()
