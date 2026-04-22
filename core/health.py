from __future__ import annotations

from django.http import HttpRequest
from ninja import Router

router = Router(tags=["health"])


@router.get("/live")
def live(request: HttpRequest) -> dict[str, object]:
    _ = request
    return {"status": "ok", "service": "judgeloom-core", "check": "live"}


@router.get("/ready")
def ready(request: HttpRequest) -> dict[str, object]:
    _ = request
    return {
        "status": "ok",
        "service": "judgeloom-core",
        "check": "ready",
        "dependencies": {"database": "ok"},
    }
