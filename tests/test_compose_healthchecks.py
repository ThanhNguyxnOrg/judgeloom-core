"""Regression checks for services sharing the production Django image."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("docker") is None, reason="requires the Docker Compose CLI")
def test_production_background_service_healthchecks() -> None:
    root = Path(__file__).resolve().parents[1]
    model = subprocess.check_output(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.prod.yml",
            "config",
            "--no-env-resolution",
            "--format",
            "json",
        ],
        cwd=root,
        text=True,
    )
    services = json.loads(model)["services"]
    for service, node in (("celery_worker", "celery"), ("celery_beat", "celerybeat")):
        kind, command = services[service]["healthcheck"]["test"]
        assert kind == "CMD-SHELL"
        assert {"inspect", "ping", "--destination", f"{node}@$$HOSTNAME"} <= set(shlex.split(command))
    assert services["celery_beat"]["environment"]["CELERY_BEAT_REMOTE_CONTROL"] == "true"

    flower = services["flower"]
    port = next(arg.removeprefix("--port=") for arg in flower["command"] if arg.startswith("--port="))
    assert f"http://127.0.0.1:{port}/healthcheck" in flower["healthcheck"]["test"]
