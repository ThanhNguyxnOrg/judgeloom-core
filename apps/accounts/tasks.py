from __future__ import annotations

from celery import shared_task

from apps.accounts.services.account_maintenance_service import AccountMaintenanceService


@shared_task(
    bind=True,
    name="accounts.cleanup_expired_sessions",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def cleanup_expired_sessions(self: object) -> int:
    """Delete expired Django sessions.

    Args:
        self: Celery task instance.

    Returns:
        Number of removed sessions.
    """

    return AccountMaintenanceService.cleanup_expired_sessions()


@shared_task(
    bind=True,
    name="accounts.send_welcome_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_welcome_email(self: object, user_id: int) -> None:
    """Send onboarding email for a newly registered user.

    Args:
        self: Celery task instance.
        user_id: Primary key of the user.
    """

    AccountMaintenanceService.send_welcome_email(user_id)
