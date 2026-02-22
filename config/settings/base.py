"""
JudgeLoom — Base Settings
=========================

Shared configuration for all environments. Environment-specific modules
(development, production, testing) import from here and override as needed.

Settings are loaded from environment variables via django-environ so that
secrets never live in source control.
"""

from __future__ import annotations

from pathlib import Path

import environ

# ─── Paths ──────────────────────────────────────────────────────────────────

# judgeloom-core/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
)

# Read .env file if it exists (ignored in production where env vars are injected)
_env_file = BASE_DIR / ".env"
if _env_file.is_file():
    env.read_env(str(_env_file))


# ─── Core ───────────────────────────────────────────────────────────────────

SECRET_KEY: str = env("DJANGO_SECRET_KEY")

DEBUG: bool = env("DJANGO_DEBUG")

ALLOWED_HOSTS: list[str] = env("DJANGO_ALLOWED_HOSTS")

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ─── Applications ──────────────────────────────────────────────────────────

DJANGO_APPS: list[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS: list[str] = [
    "channels",
    "django_celery_beat",
    "django_extensions",
    "django_otp",
    "django_otp.plugins.otp_totp",
]

LOCAL_APPS: list[str] = [
    "apps.accounts",
    "apps.organizations",
    "apps.problems",
    "apps.submissions",
    "apps.contests",
    "apps.judge",
    "apps.content",
    "apps.tickets",
    "apps.ratings",
    "apps.tags",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# ─── Middleware ─────────────────────────────────────────────────────────────

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.TimezoneMiddleware",
    "core.middleware.RequestMetricsMiddleware",
    "core.middleware.RateLimitMiddleware",
]


# ─── Templates ──────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ─── Database ──────────────────────────────────────────────────────────────

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://judgeloom:judgeloom@localhost:5432/judgeloom"),
}

DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True


# ─── Cache ─────────────────────────────────────────────────────────────────

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "jl",
        "TIMEOUT": 300,
    },
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"


# ─── Channel Layers (WebSocket) ───────────────────────────────────────────

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("CHANNEL_LAYERS_URL", default="redis://localhost:6379/2")],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}


# ─── Celery ────────────────────────────────────────────────────────────────

CELERY_BROKER_URL: str = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND: str = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT: list[str] = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 minutes soft limit
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fair scheduling for judge tasks
CELERY_TASK_ACKS_LATE = True  # Re-queue on worker crash
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"


# ─── Auth ──────────────────────────────────────────────────────────────────

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS: list[str] = [
    "apps.accounts.backends.JudgeLoomBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ─── Internationalization ──────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# ─── Static & Media ───────────────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", default=str(BASE_DIR / "static_collected"))
STATICFILES_DIRS: list[str] = [str(BASE_DIR / "static")]

MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))


# ─── Logging ───────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {module}.{funcName}:{lineno} — {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {name} — {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# ─── JudgeLoom Platform Settings ──────────────────────────────────────────

JUDGELOOM = {
    # Judge bridge connection
    "BRIDGE_HOST": env("JUDGE_BRIDGE_HOST", default="localhost"),
    "BRIDGE_PORT": env.int("JUDGE_BRIDGE_PORT", default=9999),
    "BRIDGE_SECRET": env("JUDGE_BRIDGE_SECRET", default="change-me"),
    # Submission defaults
    "DEFAULT_TIME_LIMIT": 2.0,  # seconds
    "DEFAULT_MEMORY_LIMIT": 262144,  # KB (256 MB)
    "MAX_SUBMISSION_SIZE": 65536,  # bytes (64 KB source)
    "SUBMISSION_RATE_LIMIT": "10/m",  # per user
    "API_RATE_LIMIT": "100/m",  # per IP for /api/ endpoints
    # Contest defaults
    "DEFAULT_CONTEST_DURATION": 18000,  # seconds (5 hours)
    "RATING_FLOOR": 0,
    "RATING_INITIAL": 1500,
    # Content rendering
    "MARKDOWN_EXTENSIONS": [
        "fenced_code",
        "tables",
        "codehilite",
        "toc",
        "nl2br",
    ],
    # Pagination
    "DEFAULT_PAGE_SIZE": 50,
    "MAX_PAGE_SIZE": 200,
}
