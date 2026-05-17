"""
JudgeLoom — Production Settings
================================

Extends base settings with hardened security, connection pooling,
and error monitoring via Sentry. All secrets loaded from environment.
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import MIDDLEWARE, env

# ─── Security ──────────────────────────────────────────────────────────────

DEBUG = False

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True


# ─── CORS ──────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "corsheaders",
    *INSTALLED_APPS,  # noqa: F405
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    *MIDDLEWARE,
]

CORS_ALLOWED_ORIGINS: list[str] = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True


# ─── Static Files ─────────────────────────────────────────────────────────

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")


# ─── Sentry ────────────────────────────────────────────────────────────────

_sentry_dsn = env("SENTRY_DSN", default="")

if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(level=None, event_level="ERROR"),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )


# ─── Logging ──────────────────────────────────────────────────────────────

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
