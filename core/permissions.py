"""
JudgeLoom — Core Permissions
==============================

Reusable permission classes for Django Ninja API endpoints.
These are called by endpoint decorators to guard access.

Classes:
    IsAuthenticated: Requires a logged-in user.
    IsStaff: Requires ``is_staff`` flag.
    IsSuperuser: Requires ``is_superuser`` flag.
    IsObjectOwner: Checks ownership via a configurable field.
    HasProblemAccess: Checks the user can view a specific problem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from ninja.security import HttpBearer

if TYPE_CHECKING:
    from django.http import HttpRequest

    from apps.accounts.models import User


class JudgeLoomAuth(HttpBearer):
    """JWT bearer token authentication for the API.

    Validates the ``Authorization: Bearer <token>`` header and
    attaches the authenticated user to the request.
    """

    def authenticate(self, request: HttpRequest, token: str) -> User | None:
        """Decode and validate a JWT token.

        Args:
            request: The incoming HTTP request.
            token: The raw bearer token string.

        Returns:
            The authenticated User instance, or None if invalid.
        """
        UserModel = get_user_model()  # noqa: N806 — Django model class

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
            )
        except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
            return None

        # Auth service uses "sub" for user_id. Fallback to "user_id" for old tokens.
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            return None

        try:
            user = UserModel.objects.get(pk=user_id, is_active=True, is_banned=False)
        except UserModel.DoesNotExist:
            return None

        return user  # type: ignore[return-value]


def is_authenticated(request: HttpRequest) -> bool:
    """Check that the request comes from an authenticated user.

    Args:
        request: The incoming HTTP request.

    Returns:
        True if the user is logged in and active.
    """
    return bool(hasattr(request, "user") and request.user.is_authenticated and request.user.is_active)


def is_staff(request: HttpRequest) -> bool:
    """Check that the request comes from a staff member.

    Args:
        request: The incoming HTTP request.

    Returns:
        True if the user has the ``is_staff`` flag.
    """
    return is_authenticated(request) and request.user.is_staff


def is_superuser(request: HttpRequest) -> bool:
    """Check that the request comes from a superuser.

    Args:
        request: The incoming HTTP request.

    Returns:
        True if the user has the ``is_superuser`` flag.
    """
    return is_authenticated(request) and request.user.is_superuser


def is_object_owner(request: HttpRequest, obj: Any, owner_field: str = "user") -> bool:
    """Check that the requesting user owns the given object.

    Args:
        request: The incoming HTTP request.
        obj: The model instance to check ownership of.
        owner_field: The attribute name on ``obj`` that references the owner.

    Returns:
        True if the user matches the owner.
    """
    if not is_authenticated(request):
        return False
    owner = getattr(obj, owner_field, None)
    return owner is not None and owner.pk == request.user.pk
