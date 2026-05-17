"""
JudgeLoom — Celery Application
================================

Configures the Celery instance for distributed task processing.
Auto-discovers tasks from all installed apps.

Usage::

    # Start worker
    celery -A config worker --loglevel=info

    # Start beat scheduler
    celery -A config beat --loglevel=info
"""

from __future__ import annotations

import os

from celery import Celery
from celery.signals import setup_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("judgeloom")

# Load config from Django settings, using the CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps (apps/*/tasks.py)
app.autodiscover_tasks()


@setup_logging.connect  # type: ignore[misc]
def configure_logging(**kwargs: object) -> None:
    """Use Django's logging configuration for Celery workers.

    This prevents Celery from overriding the logging setup defined
    in Django settings, ensuring consistent log formatting.
    """
    import logging.config

    from django.conf import settings

    logging.config.dictConfig(settings.LOGGING)


@app.task(bind=True, ignore_result=True)
def debug_task(self: Celery) -> None:
    """Diagnostic task for verifying Celery connectivity.

    Prints the current request info to the worker log. Useful for
    testing that the broker, backend, and worker are wired correctly.
    """
    print(f"Request: {self.request!r}")
