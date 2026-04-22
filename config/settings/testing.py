"""
JudgeLoom — Testing Settings
==============================

Optimized for fast test execution: in-memory SQLite, hashed passwords
disabled, synchronous Celery, and minimal logging.
"""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "testing-secret-key-not-for-production")

from .base import *  # noqa: F401,F403

# ─── Core ───────────────────────────────────────────────────────────────────

DEBUG = False

SECRET_KEY = "testing-secret-key-not-for-production"  # noqa: S105

ALLOWED_HOSTS = ["*"]


# ─── Database ──────────────────────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}


# ─── Cache ─────────────────────────────────────────────────────────────────

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}


# ─── Channel Layers ───────────────────────────────────────────────────────

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


# ─── Auth ──────────────────────────────────────────────────────────────────

# Disable password validators for test speed
AUTH_PASSWORD_VALIDATORS = []

# Use fast hasher
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]


# ─── Email ─────────────────────────────────────────────────────────────────

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


# ─── Celery ────────────────────────────────────────────────────────────────

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True


# ─── Logging ──────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
        "level": "CRITICAL",
    },
}
