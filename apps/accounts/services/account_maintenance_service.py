from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.utils import timezone

from core.cache import invalidate_pattern
from core.events import Event, USER_REGISTERED, publish_sync


class AccountMaintenanceService:
    """Service layer for account lifecycle maintenance tasks."""

    @staticmethod
    def cleanup_expired_sessions() -> int:
        """Delete expired Django sessions.

        Returns:
            Number of removed session records.
        """

        deleted_count, _details = Session.objects.filter(expire_date__lt=timezone.now()).delete()
        invalidate_pattern("jl:session:")
        return int(deleted_count)

    @staticmethod
    def send_welcome_email(user_id: int) -> None:
        """Send a welcome email and publish user registration event.

        Args:
            user_id: Primary key of the target user.
        """

        user_model = get_user_model()
        user = user_model.objects.filter(id=user_id).first()
        if user is None:
            return

        if user.email:
            send_mail(
                subject="Welcome to JudgeLoom",
                message=(
                    f"Hi {user.username},\n\n"
                    "Welcome to JudgeLoom. Your account is ready and you can start solving problems now."
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )

        publish_sync(
            Event(
                type=USER_REGISTERED,
                payload={"user_id": user.id, "username": user.username},
            )
        )

    @staticmethod
    def refresh_user_submission_stats(user_id: int) -> None:
        """Recalculate solved-problem count and points for a user.

        Args:
            user_id: Primary key of the user.
        """

        user_model = get_user_model()
        user = user_model.objects.filter(id=user_id).first()
        if user is None:
            return

        accepted_submissions = user.submissions.filter(result="AC").select_related("problem")
        solved_problem_ids = set(accepted_submissions.values_list("problem_id", flat=True))
        total_points = 0.0
        for problem_id in solved_problem_ids:
            best_points = (
                user.submissions.filter(problem_id=problem_id)
                .order_by("-points")
                .values_list("points", flat=True)
                .first()
            )
            total_points += float(best_points or 0.0)

        user.problem_count = len(solved_problem_ids)
        user.points = round(total_points, 2)
        user.performance_points = round(total_points * 0.1, 2)
        user.save(update_fields=["problem_count", "points", "performance_points", "updated_at"])

        invalidate_pattern(f"jl:user:{user.id}")

    @staticmethod
    def cleanup_inactive_user_cache(retention_days: int = 30) -> int:
        """Invalidate stale user cache namespace.

        Args:
            retention_days: Retention period in days.

        Returns:
            Count hint for cleanup actions.
        """

        _ = timezone.now() - timedelta(days=retention_days)
        invalidate_pattern("jl:user:")
        return 1
