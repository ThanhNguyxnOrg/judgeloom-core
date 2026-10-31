from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import connection
from django.http import JsonResponse
from ninja import Router

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)

router = Router(tags=["health"])


@router.get("/live")
def live(request: HttpRequest) -> dict[str, object]:
    _ = request
    return {"status": "ok", "service": "judgeloom-core", "check": "live"}


@router.get("/ready")
def ready(request: HttpRequest) -> dict[str, object] | JsonResponse:
    _ = request
    try:
        connection.ensure_connection()
        connection.cursor().execute("SELECT 1")
    except Exception:
        logger.exception("Readiness database check failed")
        return JsonResponse(
            {
                "status": "error",
                "service": "judgeloom-core",
                "check": "ready",
                "dependencies": {"database": "error"},
            },
            status=503,
        )

    return {
        "status": "ok",
        "service": "judgeloom-core",
        "check": "ready",
        "dependencies": {"database": "ok"},
    }
