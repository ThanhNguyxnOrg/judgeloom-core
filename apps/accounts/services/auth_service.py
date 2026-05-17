from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model

from core.exceptions import ValidationError

if TYPE_CHECKING:
    from apps.accounts.models import User

    pass


class AuthService:
    """Authentication and account security operations."""

    ACCESS_TOKEN_HOURS: int = 24
    JWT_ALGORITHM: str = "HS256"

    @staticmethod
    def _user_model() -> type[User]:
        """Return configured Django user model as typed class."""

        return cast("type[User]", get_user_model())

    @staticmethod
    def create_user(username: str, email: str, password: str) -> User:
        """Create a new user with normalized identity fields.

        Args:
            username: Desired unique username.
            email: User email address.
            password: Raw password value.

        Returns:
            Persisted user instance.

        Raises:
            ValidationError: If user identity data is invalid or duplicates exist.
        """

        user_model = AuthService._user_model()

        normalized_username = username.strip()
        normalized_email = email.strip().lower()
        if not normalized_username:
            raise ValidationError("Username is required.")
        if not normalized_email:
            raise ValidationError("Email is required.")
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters.")

        if user_model.objects.filter(username__iexact=normalized_username).exists():
            raise ValidationError("Username is already in use.")
        if user_model.objects.filter(email__iexact=normalized_email).exists():
            raise ValidationError("Email is already in use.")

        return user_model.objects.create_user(
            username=normalized_username,
            email=normalized_email,
            password=password,
        )

    @staticmethod
    def authenticate(username_or_email: str, password: str) -> User | None:
        """Authenticate user using username or email.

        Args:
            username_or_email: Login identity value.
            password: Raw candidate password.

        Returns:
            Authenticated user when credentials are valid, otherwise ``None``.
        """

        user_model = AuthService._user_model()
        identity = username_or_email.strip()
        if not identity or not password:
            return None

        user = user_model.objects.filter(username__iexact=identity).first()
        if user is None:
            user = user_model.objects.filter(email__iexact=identity).first()
        if user is None:
            return None
        if user.is_banned:
            return None
        if not user.check_password(password):
            return None
        if not user.is_active:
            return None
        return user

    @classmethod
    def generate_jwt_token(cls, user: User) -> str:
        """Generate an access JWT token for a user.

        Args:
            user: User instance.

        Returns:
            Signed JWT token string.
        """

        now = datetime.now(UTC)
        payload: dict[str, str | int] = {
            "sub": str(user.pk),
            "username": user.username,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=cls.ACCESS_TOKEN_HOURS)).timestamp()),
        }
        return str(jwt.encode(payload, settings.SECRET_KEY, algorithm=cls.JWT_ALGORITHM))

    @classmethod
    def refresh_jwt_token(cls, token: str) -> str:
        """Refresh a valid access token by issuing a new one.

        Args:
            token: Existing signed JWT token.

        Returns:
            Fresh signed JWT token string.

        Raises:
            ValidationError: If token is invalid or user no longer exists.
        """

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[cls.JWT_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise ValidationError("Invalid token.") from exc

        token_type = payload.get("type")
        if token_type != "access":
            raise ValidationError("Unsupported token type.")

        user_model = cls._user_model()
        user_id_value = payload.get("sub")
        user_id = str(user_id_value) if user_id_value is not None else ""
        user = user_model.objects.filter(pk=user_id).first()
        if user is None:
            raise ValidationError("User not found for token.")
        if user.is_banned or not user.is_active:
            raise ValidationError("User cannot refresh token.")

        return cls.generate_jwt_token(user)

    @staticmethod
    def change_password(user: User, old_password: str, new_password: str) -> None:
        """Change password for a user after old password verification.

        Args:
            user: User whose password will be changed.
            old_password: Existing password.
            new_password: New password.

        Raises:
            ValidationError: If old password is wrong or new password is weak.
        """

        if not user.check_password(old_password):
            raise ValidationError("Old password is incorrect.")
        if len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters.")

        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])

    @staticmethod
    def generate_api_token(user: User) -> str:
        """Generate and persist a new API token for a user.

        Args:
            user: User whose API token should be updated.

        Returns:
            Newly generated API token.
        """

        token = secrets.token_urlsafe(48)
        user.api_token = token
        user.save(update_fields=["api_token", "updated_at"])
        return token

    @staticmethod
    def ban_user(user: User, reason: str) -> None:
        """Ban a user from authentication and update audit fields.

        Args:
            user: User to ban.
            reason: Ban rationale.
        """

        user.is_banned = True
        user.ban_reason = reason.strip()
        user.save(update_fields=["is_banned", "ban_reason", "updated_at"])

    @staticmethod
    def unban_user(user: User) -> None:
        """Remove ban status and clear ban reason.

        Args:
            user: User to unban.
        """

        user.is_banned = False
        user.ban_reason = ""
        user.save(update_fields=["is_banned", "ban_reason", "updated_at"])
