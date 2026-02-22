from __future__ import annotations

from typing import Any

from channels.generic.websocket import AsyncJsonWebSocketConsumer


class JudgeStatusConsumer(AsyncJsonWebSocketConsumer):
    """Streams judge health/status and queue metrics to staff clients."""

    group_name: str

    async def connect(self) -> None:
        """Accept connection for staff users and subscribe to judge updates.

        This consumer is restricted to authenticated staff users to avoid
        exposing operational status to unprivileged clients.
        """

        user = self.scope.get("user")
        if user is None or not getattr(user, "is_authenticated", False) or not getattr(user, "is_staff", False):
            await self.close(code=4403)
            return

        self.group_name = "judges"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        """Leave the judges group on disconnect.

        Args:
            close_code: WebSocket close status code.
        """

        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        """Handle incoming JSON messages from the client.

        Supported client messages:
            - ``{"type": "ping"}`` -> responds with ``{"type": "pong"}``

        Args:
            content: Incoming JSON payload.
            **kwargs: Additional Channels kwargs.
        """

        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def judge_update(self, event: dict[str, Any]) -> None:
        """Forward judge status updates to the WebSocket client.

        Expects a Channels group event with a ``payload`` dict.

        Args:
            event: Channel-layer event payload.
        """

        payload: dict[str, Any] = event.get("payload") or {}
        payload.setdefault("type", "judge.update")
        await self.send_json(payload)

    async def queue_update(self, event: dict[str, Any]) -> None:
        """Forward judge queue size updates to the WebSocket client.

        Expects a Channels group event with a ``payload`` dict.

        Args:
            event: Channel-layer event payload.
        """

        payload: dict[str, Any] = event.get("payload") or {}
        payload.setdefault("type", "judge.queue.update")
        await self.send_json(payload)
