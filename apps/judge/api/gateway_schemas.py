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


class JudgeClaimIn(Schema):
    """Worker request for one queued job."""

    languages: list[str] = Field(default_factory=list)
    max_jobs: int = 1
    wait_seconds: int = 0


class JudgeCaseIn(Schema):
    case_number: int
    status: str
    time_used: float = 0.0
    memory_used: int = 0
    points: float = 0.0
    total_points: float = 0.0
    feedback: str = ""
    output: str = ""


class JudgeCasesIn(Schema):
    cases: list[JudgeCaseIn] = Field(default_factory=list)


class JudgeFinishIn(Schema):
    status: str = "completed"
    result: str | None = None
    points: float = 0.0
    time_used: float = 0.0
    memory_used: int = 0
    case_total: int = 0
    case_passed: int = 0
    error_message: str = ""


class JudgeFailIn(Schema):
    status: str = "error"
    result: str = "IE"
    error_message: str = ""
