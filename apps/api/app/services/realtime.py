"""
Server-Sent Events (SSE) real-time layer backed by Redis pub/sub.

Why SSE rather than WebSockets: SSE is one-directional (server → client) which
is all the inbox needs for new-message notifications — the browser already has
the `send` API via REST. SSE works over plain HTTP, so it passes through the
Next.js rewrite proxy without a WS-upgrade dance, and reconnects automatically
on disconnect.

Channel naming
--------------
  conv:{conversation_id}:msg   — new / updated messages for a single thread
"""

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings

_KEEPALIVE_SECONDS = 25.0
_POLL_TIMEOUT = 1.0


async def publish_new_message(conversation_id: str, message_data: dict) -> None:
    """Publish a serialised MessageResponse to the conversation's channel.

    Swallows all errors — a Redis outage must never break the HTTP response
    that triggered the publish (webhook 200, agent send 201, etc.).
    """
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.publish(f"conv:{conversation_id}:msg", json.dumps(message_data))
    except Exception:  # noqa: BLE001
        pass
    finally:
        with contextlib.suppress(Exception):
            await r.aclose()


async def stream_conversation(conversation_id: str) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted text for a conversation thread.

    Each `data:` line carries a JSON-encoded MessageResponse object (the same
    shape as the REST endpoint). Comment lines (`:`...) are keepalive pings that
    prevent proxy/CDN timeouts; the browser's EventSource ignores them.
    """
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"conv:{conversation_id}:msg"
    await pubsub.subscribe(channel)

    yield "event: connected\ndata: {}\n\n"

    last_keepalive = time.monotonic()
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_POLL_TIMEOUT)
            if msg and msg["type"] == "message":
                yield f"data: {msg['data']}\n\n"

            if time.monotonic() - last_keepalive >= _KEEPALIVE_SECONDS:
                yield ": keepalive\n\n"
                last_keepalive = time.monotonic()
    except (GeneratorExit, asyncio.CancelledError):
        pass
    finally:
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await r.aclose()
