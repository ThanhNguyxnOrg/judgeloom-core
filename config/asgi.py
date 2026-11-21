"""
JudgeLoom — ASGI Configuration
================================

Exposes the ASGI application with Django Channels support for WebSocket
connections (real-time submission updates, contest scoreboards, etc.).

Deployment::

    daphne config.asgi:application
    uvicorn config.asgi:application
"""

from __future__ import annotations

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

from core.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        ),
    }
)
