"""
JudgeLoom — Root URL Configuration
====================================

All app-level routes are included under their respective prefixes.
The Django Ninja API is mounted at ``/api/``.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from ninja import NinjaAPI

from core.exceptions import configure_api_exception_handlers

# ─── API ────────────────────────────────────────────────────────────────────

api = NinjaAPI(
    title="JudgeLoom API",
    version="1.0.0",
    description="RESTful API for the JudgeLoom online judge platform.",
    urls_namespace="api",
)

configure_api_exception_handlers(api)

# Register API routers from each app
api.add_router("/accounts/", "apps.accounts.api.router", tags=["accounts"])
api.add_router("/organizations/", "apps.organizations.api.router", tags=["organizations"])
api.add_router("/problems/", "apps.problems.api.router", tags=["problems"])
api.add_router("/submissions/", "apps.submissions.api.router", tags=["submissions"])
api.add_router("/contests/", "apps.contests.api.router", tags=["contests"])
api.add_router("/judge/", "apps.judge.api.router", tags=["judge"])
api.add_router("/content/", "apps.content.api.router", tags=["content"])
api.add_router("/tickets/", "apps.tickets.api.router", tags=["tickets"])
api.add_router("/ratings/", "apps.ratings.api.router", tags=["ratings"])
api.add_router("/tags/", "apps.tags.api.router", tags=["tags"])
api.add_router("/health/", "core.health", tags=["health"])


# ─── URL Patterns ──────────────────────────────────────────────────────────

urlpatterns: list = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]

# Debug toolbar (development only)
if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
