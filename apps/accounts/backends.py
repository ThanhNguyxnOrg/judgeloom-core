from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

if TYPE_CHECKING:
    from django.http import HttpRequest


class JudgeLoomBackend(ModelBackend):
    """Authentication backend that supports username/email and ban checks."""

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: object,
    ) -> object | None:
        """Authenticate an active non-banned user by username or email.

        Args:
            request: Django request object.
            username: Username value, if supplied by auth form.
            password: Candidate raw password.
            **kwargs: Additional auth values.

        Returns:
            Authenticated user instance or ``None``.
        """

        user_model = get_user_model()
        if password is None:
            return None

        username_field_value = kwargs.get(user_model.USERNAME_FIELD)
        email_value = kwargs.get("email")

        identity = username
        if identity is None and isinstance(username_field_value, str):
            identity = username_field_value
        if identity is None and isinstance(email_value, str):
            identity = email_value
        if identity is None:
            return None

        user = user_model._default_manager.filter(username__iexact=identity).first()
        if user is None:
            user = user_model._default_manager.filter(email__iexact=identity).first()
        if user is None:
            return None

        if not user.check_password(password):
            return None
        if not self.user_can_authenticate(user):
            return None
        if getattr(user, "is_banned", False):
            return None
        return user

    def user_can_authenticate(self, user: object) -> bool:
        """Check standard auth rules and JudgeLoom-specific bans.

        Args:
            user: Candidate user object.

        Returns:
            ``True`` if the user can authenticate.
        """

        return super().user_can_authenticate(user) and not getattr(user, "is_banned", False)
