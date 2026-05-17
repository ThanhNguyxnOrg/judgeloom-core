from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import User, WebAuthnCredential


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin configuration for the custom user model."""

    list_display = ("username", "email", "rating", "is_staff", "is_banned")
    list_filter = ("is_staff", "is_superuser", "is_active", "is_banned", "language", "theme")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    fieldsets = (
        *DjangoUserAdmin.fieldsets,
        (
            "JudgeLoom",
            {
                "fields": (
                    "timezone",
                    "language",
                    "theme",
                    "role",
                    "display_rank",
                    "about",
                    "current_contest",
                    "rating",
                    "max_rating",
                    "points",
                    "performance_points",
                    "problem_count",
                    "is_totp_enabled",
                    "totp_key",
                    "api_token",
                    "mfa_enabled",
                    "notes",
                    "is_banned",
                    "ban_reason",
                )
            },
        ),
    )


@admin.register(WebAuthnCredential)
class WebAuthnCredentialAdmin(admin.ModelAdmin):
    """Admin configuration for WebAuthn credentials."""

    list_display = ("user", "name", "sign_count", "created_at")
    search_fields = ("user__username", "name")
    readonly_fields = ("created_at", "updated_at")
