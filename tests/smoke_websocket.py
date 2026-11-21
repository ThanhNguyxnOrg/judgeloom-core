"""Probe a deployed public contest feed through its TLS reverse proxy."""

import asyncio
import json
import sys
from urllib.parse import urlsplit

from websockets.asyncio.client import connect
from websockets.typing import Origin


async def check_feed(url: str) -> None:
    target = urlsplit(url)
    if target.scheme != "wss" or not target.netloc:
        raise ValueError("Expected a wss:// URL for a visible public contest")

    async with connect(url, origin=Origin(f"https://{target.netloc}"), open_timeout=10) as feed:
        await feed.send('{"type":"ping"}')
        async with asyncio.timeout(10):
            while json.loads(await feed.recv()) != {"type": "pong"}:
                pass  # Ranking updates may arrive before the pong.


if __name__ == "__main__":
    asyncio.run(check_feed(sys.argv[1]))
    print("Contest feed returned pong over WSS")
