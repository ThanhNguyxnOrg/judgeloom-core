from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

from config.settings.secret import MIN_SECRET_KEY_LENGTH, validate_secret_key

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "value",
    [
        "",
        "short",
        "change-me",
        "change-me-to-a-random-50-char-string",
        "dev-local-judgeloom-change-me",
        "testing-secret-key-not-for-production",
        "build-only-not-a-secret",
        "django-insecure-" + "x" * 50,
    ],
)
def test_rejects_placeholder_and_short_secret_keys(value):
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        validate_secret_key(value)


def test_accepts_generated_secret_key():
    value = get_random_secret_key()
    assert len(value) >= MIN_SECRET_KEY_LENGTH
    assert validate_secret_key(value) == value


def _import_production_settings(secret: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": secret,
            "DJANGO_ALLOWED_HOSTS": "judgeloom.example.com",
            "DJANGO_DEBUG": "False",
            "SENTRY_DSN": "",
            "DATABASE_URL": "postgres://judgeloom:test@localhost:5432/judgeloom",
        }
    )
    return subprocess.run(
        [sys.executable, "-c", "import config.settings.production"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_production_settings_rejects_placeholder_secret():
    result = _import_production_settings("change-me-to-a-random-50-char-string")
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr


def test_production_settings_accepts_generated_secret():
    result = _import_production_settings(get_random_secret_key())
    assert result.returncode == 0, result.stderr
