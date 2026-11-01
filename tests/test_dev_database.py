from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dev_database_engine(database_url: str) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.development",
            "DATABASE_URL": database_url,
            "DJANGO_SECRET_KEY": "test-only",
            "DJANGO_ALLOWED_HOSTS": "localhost",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import config.settings.development as s; print(s.DATABASES['default']['ENGINE'])",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout.strip()


def test_development_uses_postgres_when_database_url_is_set():
    engine = _dev_database_engine("postgres://judgeloom:test@localhost:5432/judgeloom")
    assert engine == "django.db.backends.postgresql"


def test_development_falls_back_to_sqlite_without_database_url():
    engine = _dev_database_engine("")
    assert engine == "django.db.backends.sqlite3"
