from __future__ import annotations

from typing import Any

from ninja import Schema
from pydantic import Field


class JudgeRegisterIn(Schema):
    """Payload sent when a worker registers or updates its capabilities."""

    protocol_version: int = 1
    capabilities: dict[str, Any] = Field(default_factory=dict)


class JudgeHeartbeatIn(Schema):
    """Periodic worker heartbeat."""

    load: float = 0.0
    running_jobs: int = 0
    cached_packages: list[str] = Field(default_factory=list)


class JudgeRegisterOut(Schema):
    judge_id: int
    heartbeat_interval: int


class JudgeHeartbeatOut(Schema):
    ok: bool
    next_heartbeat: int
