from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

MIN_SECRET_KEY_LENGTH = 50

KNOWN_INSECURE_SECRET_KEYS = frozenset(
    {
        "change-me",
        "change-me-to-a-random-50-char-string",
        "dev-insecure-key-do-not-use-in-production-judgeloom-2024",
        "dev-local-judgeloom-change-me",
        "testing-secret-key-not-for-production",
        "build-only-not-a-secret",
    }
)


def validate_secret_key(value: str) -> str:
    """Reject known placeholder or trivially short production signing keys."""

    if (
        not isinstance(value, str)
        or len(value) < MIN_SECRET_KEY_LENGTH
        or value in KNOWN_INSECURE_SECRET_KEYS
        or value.startswith("django-insecure-")
    ):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be a unique random value of at least "
            f"{MIN_SECRET_KEY_LENGTH} characters. Generate one with: "
            'python -c "from django.core.management.utils import '
            'get_random_secret_key; print(get_random_secret_key())"'
        )
    return value
