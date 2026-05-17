"""
JudgeLoom — Development Settings
=================================

Extends base settings with developer-friendly defaults: DEBUG=True,
verbose SQL logging, Django Debug Toolbar, and console email.
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import INSTALLED_APPS, MIDDLEWARE

# ─── Core ───────────────────────────────────────────────────────────────────

DEBUG = True

ALLOWED_HOSTS = ["*"]

SECRET_KEY = "dev-insecure-key-do-not-use-in-production-judgeloom-2024"


# ─── Debug Toolbar ─────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "debug_toolbar",
    *INSTALLED_APPS,
]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    *MIDDLEWARE,
]

INTERNAL_IPS = ["127.0.0.1", "::1"]

DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
}


# ─── Database ──────────────────────────────────────────────────────────────

# Use SQLite for quick local dev if DATABASE_URL is not set
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    },
}


# ─── Cache ─────────────────────────────────────────────────────────────────

# Use local memory cache for development (no Redis dependency)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "judgeloom-dev",
    },
}


# ─── Channel Layers ───────────────────────────────────────────────────────

# In-memory channel layer for development
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


# ─── Email ─────────────────────────────────────────────────────────────────

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# ─── Celery ────────────────────────────────────────────────────────────────

# Use synchronous execution in dev (no broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True


# ─── Logging ──────────────────────────────────────────────────────────────

LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "WARNING",  # Set to DEBUG to see all SQL queries
    "propagate": False,
}
