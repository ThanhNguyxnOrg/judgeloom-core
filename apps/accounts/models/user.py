from __future__ import annotations

from typing import Final

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts.constants import DisplayTheme, LanguageCode, UserRole
from core.models import TimestampedModel


class User(AbstractUser, TimestampedModel):
    """Primary user entity for authentication, profile, and ranking.

    This model extends Django's ``AbstractUser`` and adds online-judge specific
    profile, rating, security, and participation metadata.
    """

    timezone = models.CharField(max_length=64, default="UTC")
    language = models.CharField(
        max_length=8,
        choices=LanguageCode.choices,
        default=LanguageCode.EN,
    )
    theme = models.CharField(
        max_length=16,
        choices=DisplayTheme.choices,
        default=DisplayTheme.SYSTEM,
    )
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.PARTICIPANT,
    )
    display_rank = models.CharField(max_length=64, blank=True, default="")
    about = models.TextField(blank=True, default="")
    organizations = models.ManyToManyField(
        "organizations.Organization",
        related_name="members",
        blank=True,
    )
    current_contest = models.ForeignKey(
        "contests.ContestParticipation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="active_users",
    )
    rating = models.IntegerField(default=0)
    max_rating = models.IntegerField(default=0)
    points = models.FloatField(default=0.0)
    performance_points = models.FloatField(default=0.0)
    problem_count = models.PositiveIntegerField(default=0)
    is_totp_enabled = models.BooleanField(default=False)
    totp_key = models.CharField(max_length=255, null=True, blank=True)
    api_token = models.CharField(max_length=128, unique=True, null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    ban_reason = models.TextField(blank=True, default="")
    is_banned = models.BooleanField(default=False)

    _RATING_CLASSES: Final[list[tuple[int, str]]] = [
        (3000, "user-legendary-grandmaster"),
        (2600, "user-international-grandmaster"),
        (2400, "user-grandmaster"),
        (2200, "user-master"),
        (1900, "user-candidate-master"),
        (1600, "user-expert"),
        (1400, "user-specialist"),
        (1200, "user-pupil"),
        (0, "user-newbie"),
    ]

    class Meta(TimestampedModel.Meta):
        """Model metadata and database tuning hints."""

        db_table = "accounts_user"
        ordering = ["username"]
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["rating"], name="accounts_user_rating_idx"),
            models.Index(fields=["points"], name="accounts_user_points_idx"),
            models.Index(fields=["username"], name="accounts_user_username_idx"),
        ]

    def __str__(self) -> str:
        """Return the username as the string representation."""

        return self.username

    @property
    def display_name(self) -> str:
        """Return the best available display name for the user.

        Returns:
            Preferred display name, falling back to ``username``.
        """

        full_name = self.get_full_name().strip()
        return full_name if full_name else self.username

    @property
    def is_contest_participant(self) -> bool:
        """Whether the user is currently attached to a contest session.

        Returns:
            ``True`` when ``current_contest`` is set, else ``False``.
        """

        return self.current_contest_id is not None

    @property
    def css_class(self) -> str:
        """Return profile badge CSS class according to current rating.

        Returns:
            CSS class token for frontend rendering.
        """

        return self.get_rating_class()

    def get_rating_class(self) -> str:
        """Map user rating into a deterministic CSS class.

        Returns:
            CSS class name representing current rating tier.
        """

        for threshold, class_name in self._RATING_CLASSES:
            if self.rating >= threshold:
                return class_name
        return "user-newbie"

    def calculate_contribution(self) -> float:
        """Compute normalized contribution score for ranking heuristics.

        Returns:
            Contribution value that blends points, rating, and solved count.
        """

        activity_component = float(self.problem_count) * 0.2
        rating_component = max(float(self.rating), 0.0) / 1000.0
        score = self.points + self.performance_points + activity_component + rating_component
        return round(score, 3)
