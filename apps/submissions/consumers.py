from __future__ import annotations

from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.submissions.models import Submission
from apps.submissions.services import SubmissionService


class SubmissionConsumer(AsyncJsonWebsocketConsumer):
    """Streams real-time submission updates to clients via WebSocket."""

    group_name: str

    async def connect(self) -> None:
        """Accept connection and subscribe client to the submission group."""
        user = self.scope.get("user")
        submission_id = self.scope["url_route"]["kwargs"]["submission_id"]

        if user is None or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        allowed = await self._can_view_submission(user=user, submission_id=int(submission_id))
        if not allowed:
            await self.close(code=4403)
            return

        self.group_name = f"submission_{submission_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def _can_view_submission(self, user: Any, submission_id: int) -> bool:
        submission = Submission.objects.select_related("problem").filter(pk=submission_id).first()
        if submission is None:
            return False
        return SubmissionService.can_view_submission(user=user, submission=submission)

    async def disconnect(self, close_code: int) -> None:
        """Remove client from the submission group.

        Args:
            close_code: WebSocket close status code.
        """
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        """Handle incoming messages from clients.

        Args:
            content: Incoming JSON payload.
            **kwargs: Additional channel kwargs.
        """
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Forward legacy channel-layer events to the WebSocket client.

        Args:
            event: Channel event payload containing update data.
        """
        payload = event.get("payload", {})
        await self.send_json(payload)

    async def submission_status(self, event: dict[str, Any]) -> None:
        """Forward a submission status event."""

        await self.send_json(event.get("payload", {}))

    async def submission_case(self, event: dict[str, Any]) -> None:
        """Forward a per-test-case event."""

        await self.send_json(event.get("payload", {}))

    async def submission_finished(self, event: dict[str, Any]) -> None:
        """Forward a final submission event."""

        await self.send_json(event.get("payload", {}))
