from __future__ import annotations

from typing import TYPE_CHECKING

from django.apps import apps as django_apps

from core.exceptions import ValidationError

if TYPE_CHECKING:
    from apps.accounts.models import User


class ProfileService:
    """Profile and user statistics operations."""

    @staticmethod
    def update_profile(user: User, data: dict[str, str]) -> User:
        """Update editable profile fields for a user.

        Args:
            user: User instance to update.
            data: Partial profile payload.

        Returns:
            Updated user instance.

        Raises:
            ValidationError: If provided values are invalid.
        """

        editable_fields = {
            "timezone",
            "language",
            "theme",
            "display_rank",
            "about",
            "notes",
        }

        update_fields: list[str] = []
        for field_name, value in data.items():
            if field_name not in editable_fields:
                continue
            if field_name in {"timezone", "language", "theme"} and not value:
                raise ValidationError(f"{field_name} cannot be empty.")
            setattr(user, field_name, value)
            update_fields.append(field_name)

        if update_fields:
            update_fields.append("updated_at")
            user.save(update_fields=update_fields)
        return user

    @staticmethod
    def get_user_stats(user: User) -> dict[str, int | float]:
        """Collect current user statistics from related domains.

        Args:
            user: User instance.

        Returns:
            Dictionary containing aggregated statistics.
        """

        submission_count = 0

        try:
            submission_model = django_apps.get_model("submissions", "Submission")
        except LookupError:
            submission_model = None

        if submission_model is not None:
            submission_count = int(submission_model.objects.filter(user=user, mode="submit").count())

        return {
            "submission_count": submission_count,
            "solved_problem_count": int(user.problem_count),
            "rating": int(user.rating),
            "max_rating": int(user.max_rating),
            "points": float(user.points),
            "performance_points": float(user.performance_points),
            "problem_count": int(user.problem_count),
            "contributions": float(user.calculate_contribution()),
        }

    @staticmethod
    def get_rating_history(user: User) -> list[dict[str, str | int | None]]:
        """Fetch rating history entries for graphing and analytics.

        Args:
            user: User instance.

        Returns:
            List of normalized rating history records.
        """

        try:
            rating_model = django_apps.get_model("contests", "RatingChange")
        except LookupError:
            return []

        rows = rating_model.objects.filter(user=user).order_by("created_at")
        history: list[dict[str, str | int | None]] = []
        for row in rows:
            history.append(
                {
                    "contest_id": getattr(row, "contest_id", None),
                    "old_rating": getattr(row, "old_rating", None),
                    "new_rating": getattr(row, "new_rating", None),
                    "delta": getattr(row, "delta", None),
                    "created_at": str(getattr(row, "created_at", "")) or None,
                }
            )
        return history
