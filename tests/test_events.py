from __future__ import annotations

import pytest
from channels.layers import get_channel_layer

from core.events import Event, publish


@pytest.mark.asyncio
async def test_publish_uses_explicit_group_and_event_type():
    layer = get_channel_layer()
    assert layer is not None
    channel = await layer.new_channel()
    await layer.group_add("submission_1", channel)

    try:
        await publish(Event(type="submission.status", payload={"status": "AC"}), group="submission_1")
        message = await layer.receive(channel)
    finally:
        await layer.group_discard("submission_1", channel)

    assert message["type"] == "submission.status"
    assert message["payload"] == {"status": "AC"}
    assert "timestamp" in message
    assert message["source"] == "judgeloom-core"
