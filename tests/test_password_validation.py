from __future__ import annotations

import pytest
from django.test import override_settings

from apps.accounts.services.auth_service import AuthService
from core.exceptions import ValidationError


@pytest.mark.django_db
@override_settings(
    AUTH_PASSWORD_VALIDATORS=[
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    ]
)
def test_create_user_rejects_common_password():
    with pytest.raises(ValidationError, match="too common"):
        AuthService.create_user("weak-user", "weak@example.com", "password123")


@pytest.mark.django_db
@override_settings(
    AUTH_PASSWORD_VALIDATORS=[
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {"min_length": 10},
        },
    ]
)
def test_change_password_rejects_short_password(user):
    user.set_password("old-password-123")
    user.save(update_fields=["password"])

    with pytest.raises(ValidationError, match="at least 10"):
        AuthService.change_password(user, "old-password-123", "short1234")
