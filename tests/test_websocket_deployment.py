"""Keep the effective production web command pointed at the Channels app."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("docker"), reason="requires Docker Compose")
def test_production_serves_channels() -> None:
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
            "web",
        ],
        cwd=root,
        text=True,
    )
    web = json.loads(model)["services"]["web"]
    command = web.get("command")
    if command is None:
        dockerfile = (root / web["build"]["dockerfile"]).read_text().replace("\\\n", "")
        command = json.loads(next(line[4:] for line in reversed(dockerfile.splitlines()) if line.startswith("CMD ")))
    assert "config.asgi:application" in command
