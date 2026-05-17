from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib.auth import get_user_model
from ninja import Router, Schema

from apps.accounts.api.schemas import (
    TokenOut,
    UserLoginIn,
    UserProfileOut,
    UserPublicOut,
    UserRegisterIn,
    UserStatsOut,
    UserUpdateIn,
)
from apps.accounts.services.auth_service import AuthService
from apps.accounts.services.profile_service import ProfileService
from core.exceptions import NotFoundError, ValidationError
from core.permissions import JudgeLoomAuth

if TYPE_CHECKING:
    from django.http import HttpRequest

    from apps.accounts.models import User

router = Router(tags=["accounts"])


class TokenRefreshIn(Schema):
    """Payload for token refresh."""

    token: str


class ApiTokenOut(Schema):
    """Payload for generated API token."""

    api_token: str


def _request_user(request: HttpRequest) -> User:
    """Resolve authenticated user from a Ninja request object.

    Args:
        request: Incoming request object.

    Returns:
        Authenticated user instance.

    Raises:
        ValidationError: If request is unauthenticated.
    """

    user_model = cast("type[User]", get_user_model())

    auth_user = getattr(request, "auth", None)
    if isinstance(auth_user, user_model):
        return cast("User", auth_user)

    request_user = getattr(request, "user", None)
    if request_user is not None and isinstance(request_user, user_model) and request_user.is_authenticated:
        return cast("User", request_user)

    raise ValidationError("Authentication required.")


def _user_profile_out(user: User) -> UserProfileOut:
    """Convert user model instance to profile output schema."""

    return UserProfileOut(
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        timezone=user.timezone,
        language=user.language,
        theme=user.theme,
        display_rank=user.display_rank,
        about=user.about,
        rating=user.rating,
        max_rating=user.max_rating,
        points=user.points,
        performance_points=user.performance_points,
        problem_count=user.problem_count,
        is_totp_enabled=user.is_totp_enabled,
        mfa_enabled=user.mfa_enabled,
        css_class=user.css_class,
        is_banned=user.is_banned,
    )


@router.post("/register", response=TokenOut)
def register(request: HttpRequest, payload: UserRegisterIn) -> TokenOut:
    """Register a user and return an access token.

    Args:
        request: Incoming HTTP request.
        payload: Registration payload.

    Returns:
        Token response with access JWT.
    """

    _ = request
    user = AuthService.create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    token = AuthService.generate_jwt_token(user)
    return TokenOut(access_token=token)


@router.post("/login", response=TokenOut)
def login(request: HttpRequest, payload: UserLoginIn) -> TokenOut:
    """Authenticate user credentials and issue a JWT access token."""

    _ = request
    user = AuthService.authenticate(payload.username_or_email, payload.password)
    if user is None:
        raise ValidationError("Invalid credentials.")
    return TokenOut(access_token=AuthService.generate_jwt_token(user))


@router.post("/refresh", response=TokenOut)
def refresh_token(request: HttpRequest, payload: TokenRefreshIn) -> TokenOut:
    """Refresh an existing JWT token."""

    _ = request
    return TokenOut(access_token=AuthService.refresh_jwt_token(payload.token))


@router.get("/me", response=UserProfileOut, auth=JudgeLoomAuth())
def me(request: HttpRequest) -> UserProfileOut:
    """Return currently authenticated user profile."""

    user = _request_user(request)
    return _user_profile_out(user)


@router.patch("/me", response=UserProfileOut, auth=JudgeLoomAuth())
def update_me(request: HttpRequest, payload: UserUpdateIn) -> UserProfileOut:
    """Patch currently authenticated user profile fields."""

    user = _request_user(request)
    update_data = {key: str(value) for key, value in payload.model_dump(exclude_none=True).items()}
    updated = ProfileService.update_profile(user, update_data)
    return _user_profile_out(updated)


@router.get("/{username}", response=UserPublicOut)
def public_profile(request: HttpRequest, username: str) -> UserPublicOut:
    """Return public profile for a username."""

    _ = request
    user_model = cast("type[User]", get_user_model())
    user = user_model.objects.filter(username__iexact=username).first()
    if user is None:
        raise NotFoundError("User not found.")

    return UserPublicOut(
        username=user.username,
        display_name=user.display_name,
        rating=user.rating,
        max_rating=user.max_rating,
        points=user.points,
        problem_count=user.problem_count,
        css_class=user.css_class,
    )


@router.get("/{username}/stats", response=UserStatsOut)
def user_stats(request: HttpRequest, username: str) -> UserStatsOut:
    """Return aggregate statistics for a public user profile."""

    _ = request
    user_model = cast("type[User]", get_user_model())
    user = user_model.objects.filter(username__iexact=username).first()
    if user is None:
        raise NotFoundError("User not found.")

    return UserStatsOut(**ProfileService.get_user_stats(user))


@router.post("/me/api-token", response=ApiTokenOut, auth=JudgeLoomAuth())
def create_api_token(request: HttpRequest) -> ApiTokenOut:
    """Generate a new API token for the authenticated user."""

    user = _request_user(request)
    token = AuthService.generate_api_token(user)
    return ApiTokenOut(api_token=token)
