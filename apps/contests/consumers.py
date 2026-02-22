from __future__ import annotations

from typing import Any

from channels.generic.websocket import AsyncJsonWebSocketConsumer

from core.events import CONTEST_ENDED, CONTEST_RANKING_UPDATED, CONTEST_STARTED


class ContestConsumer(AsyncJsonWebSocketConsumer):
    """Streams live contest updates (ranking and lifecycle events) to clients."""

    contest_key: str
    group_name: str

    async def connect(self) -> None:
        """Accept the WebSocket connection and join the contest group.

        The contest key is taken from the URL path and used to subscribe the
        connection to a channel-layer group named ``contest_{contest_key}``.
        """

        self.contest_key = self.scope["url_route"]["kwargs"]["contest_key"]
        self.group_name = f"contest_{self.contest_key}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        """Leave the contest group on WebSocket disconnect.

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

    async def ranking_update(self, event: dict[str, Any]) -> None:
        """Forward contest ranking updates to the WebSocket client.

        Expects a Channels group event with a ``payload`` dictionary containing
        ranking data.

        Args:
            event: Channel-layer event payload.
        """

        payload: dict[str, Any] = event.get("payload") or {}
        payload.setdefault("type", CONTEST_RANKING_UPDATED)
        await self.send_json(payload)

    async def contest_event(self, event: dict[str, Any]) -> None:
        """Forward contest lifecycle events to the WebSocket client.

        This handler is designed for events such as contest started/ended or
        contest frozen/unfrozen. Producers should provide a ``payload`` dict.

        Args:
            event: Channel-layer event payload.
        """

        payload: dict[str, Any] = event.get("payload") or {}

        event_type = payload.get("type")
        if event_type is None and isinstance(event.get("event_type"), str):
            event_type = event["event_type"]

        if event_type is None:
            event_type = "contest.event"

        allowed = {CONTEST_STARTED, CONTEST_ENDED, "contest.frozen", "contest.unfrozen"}
        if event_type in allowed:
            payload["type"] = event_type
        else:
            payload.setdefault("type", event_type)

        await self.send_json(payload)
