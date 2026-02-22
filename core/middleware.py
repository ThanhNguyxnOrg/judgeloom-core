"""
JudgeLoom — Core Middleware
==============================

Custom middleware classes for cross-cutting concerns.

Classes:
    TimezoneMiddleware: Activates user-preferred timezone per request.
    RequestMetricsMiddleware: Logs request duration for monitoring.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone as dj_timezone

from core.exceptions import RateLimitError

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class TimezoneMiddleware:
    """Activate the user's preferred timezone for each request.

    Reads ``timezone`` from the user profile (if authenticated) and
    calls ``django.utils.timezone.activate()`` so that template
    rendering and date formatting use the correct local time.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request with timezone activation.

        Args:
            request: The incoming HTTP request.

        Returns:
            The HTTP response from downstream middleware/views.
        """
        if hasattr(request, "user") and request.user.is_authenticated:
            user_tz = getattr(request.user, "timezone", None)
            if user_tz:
                try:
                    dj_timezone.activate(user_tz)
                except Exception:  # noqa: BLE001 — invalid tz should not crash
                    dj_timezone.deactivate()
            else:
                dj_timezone.deactivate()
        else:
            dj_timezone.deactivate()

        return self.get_response(request)


class RequestMetricsMiddleware:
    """Log request processing time for basic performance monitoring.

    Emits an INFO log line with the method, path, status code, and
    elapsed milliseconds for every request. In production this feeds
    into structured logging / Sentry performance tracing.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Measure and log request duration.

        Args:
            request: The incoming HTTP request.

        Returns:
            The HTTP response from downstream middleware/views.
        """
        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Skip static file requests to reduce log noise
        if not request.path.startswith(("/static/", "/media/", "/__debug__/")):
            logger.info(
                "%s %s → %d (%.1fms)",
                request.method,
                request.path,
                response.status_code,
                elapsed_ms,
            )

        return response


class RateLimitMiddleware:
    """Enforce a simple IP-based rate limit for API endpoints.

    This middleware applies only to request paths starting with ``/api/``.
    Request counts are tracked in Django's configured cache backend
    (Redis via ``django_redis`` in production).

    The rate limit is configured via ``settings.JUDGELOOM["API_RATE_LIMIT"]``
    using the format ``"<count>/<unit>"`` (e.g. ``"100/m"``). Supported
    units are seconds (s), minutes (m), hours (h), and days (d).
    """

    def __init__(self, get_response: "Callable[[HttpRequest], HttpResponse]") -> None:
        """Initialize the middleware and parse its rate limit configuration.

        Args:
            get_response: Downstream request handler.
        """

        self.get_response = get_response

        spec = str(settings.JUDGELOOM.get("API_RATE_LIMIT", "100/m"))
        self.limit, self.window_seconds = self._parse_rate_limit_spec(spec)

    @staticmethod
    def _parse_rate_limit_spec(spec: str) -> tuple[int, int]:
        """Parse a human-readable rate limit specification.

        Args:
            spec: String in the form ``"<count>/<unit>"``.

        Returns:
            A tuple of (limit, window_seconds).

        Raises:
            ValueError: If the specification cannot be parsed.
        """

        raw = spec.strip()
        if "/" not in raw:
            raise ValueError(f"Invalid rate limit spec: {spec!r}")

        count_raw, unit_raw = raw.split("/", 1)
        limit = int(count_raw.strip())

        unit = unit_raw.strip().lower()
        unit_map: dict[str, int] = {
            "s": 1,
            "sec": 1,
            "secs": 1,
            "second": 1,
            "seconds": 1,
            "m": 60,
            "min": 60,
            "mins": 60,
            "minute": 60,
            "minutes": 60,
            "h": 3600,
            "hr": 3600,
            "hrs": 3600,
            "hour": 3600,
            "hours": 3600,
            "d": 86400,
            "day": 86400,
            "days": 86400,
        }

        if unit not in unit_map:
            raise ValueError(f"Unsupported rate limit unit: {unit!r}")

        window_seconds = unit_map[unit]
        if limit <= 0 or window_seconds <= 0:
            raise ValueError(f"Invalid rate limit values: {spec!r}")

        return limit, window_seconds

    @staticmethod
    def _get_client_ip(request: "HttpRequest") -> str:
        """Resolve the client IP address from the request.

        Prefers ``X-Forwarded-For`` (first hop) when present.

        Args:
            request: Incoming HTTP request.

        Returns:
            A best-effort client IP string.
        """

        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if isinstance(forwarded_for, str) and forwarded_for.strip():
            return forwarded_for.split(",", 1)[0].strip()
        return str(request.META.get("REMOTE_ADDR", "unknown"))

    def __call__(self, request: "HttpRequest") -> "HttpResponse":
        """Apply rate limiting to API requests.

        Args:
            request: Incoming HTTP request.

        Returns:
            A 429 JSON response when the limit is exceeded, otherwise the
            downstream response.
        """

        if not request.path.startswith("/api/"):
            return self.get_response(request)

        ip = self._get_client_ip(request)
        now = time.time()
        window = int(now // self.window_seconds)
        key = f"ratelimit:{ip}:{window}"

        cache.add(key, 0, timeout=self.window_seconds)
        try:
            current = int(cache.incr(key))
        except ValueError:
            cache.set(key, 1, timeout=self.window_seconds)
            current = 1

        if current <= self.limit:
            return self.get_response(request)

        reset_at = (window + 1) * self.window_seconds
        retry_after = max(0, int(reset_at - now))

        error = RateLimitError()
        response = JsonResponse(error.as_response_body(), status=error.status_code)
        response["Retry-After"] = str(retry_after)
        return response
