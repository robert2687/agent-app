"""Shared SSE (Server-Sent Events) streaming helper.

Any topic on the event bus can be streamed: the endpoint first replays the
backlog of persisted events (honouring ``Last-Event-ID``) and then follows the
live bus until a terminal predicate is satisfied.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

from fastapi.responses import StreamingResponse

from app.api.deps import Container
from app.services.event_bus import BusEvent

TerminalCheck = Callable[[], Awaitable[bool]]
_KEEPALIVE_SECONDS = 15.0


async def stream_topic(
    container: Container,
    topic: str,
    *,
    terminal_check: TerminalCheck | None = None,
    replay: list[dict[str, Any]] | None = None,
    replay_fetcher: Callable[[int], Awaitable[list[dict[str, Any]]]] | None = None,
) -> StreamingResponse:
    """Produce a ``text/event-stream`` response for one bus topic."""
    return StreamingResponse(
        _event_source(container, topic, terminal_check, replay, replay_fetcher),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _event_source(
    container: Container,
    topic: str,
    terminal_check: TerminalCheck | None,
    replay: list[dict[str, Any]] | None,
    replay_fetcher: Callable[[int], Awaitable[list[dict[str, Any]]]] | None,
):
    """Async generator implementing the SSE protocol."""
    last_id = 0

    # ── Backlog replay ─────────────────────────────────────────────────────
    if replay is not None:
        for event in replay:
            last_id = max(last_id, int(event.get("seq") or 0))
            yield _format_sse(event.get("type", "message"), event.get("data", {}), last_id)
    elif replay_fetcher is not None:
        for event in await replay_fetcher(last_id):
            last_id = max(last_id, int(event.get("seq") or 0))
            yield _format_sse(event.get("type", "message"), event.get("data", {}), last_id)

    # ── Live follow ────────────────────────────────────────────────────────
    subscription = container.bus.subscribe(topic)
    try:
        while True:
            if terminal_check is not None and await terminal_check():
                yield _format_sse("stream.end", {"topic": topic}, None)
                return
            event = await subscription.next_event(timeout=_KEEPALIVE_SECONDS)
            if event is None:
                yield f": keepalive {int(asyncio.get_event_loop().time())}\n\n"
                continue
            seq = event.seq
            payload: dict[str, Any] = dict(event.data)
            payload.setdefault("topic", topic)
            yield _format_sse(event.type, payload, seq)
            if event.type in ("job.completed", "job.failed", "job.cancelled", "stream.end"):
                return
    finally:
        container.bus.unsubscribe(subscription)


def _format_sse(event_type: str, data: dict[str, Any], seq: int | None) -> str:
    """Encode one SSE frame."""
    lines = json.dumps(data, default=str, ensure_ascii=False).splitlines() or ["{}"]
    parts = [f"event: {event_type}"]
    if seq is not None:
        parts.append(f"id: {seq}")
    parts.extend(f"data: {line}" for line in lines)
    return "\n".join(parts) + "\n\n"


def bus_event_to_dict(event: BusEvent) -> dict[str, Any]:
    """Normalize a BusEvent into the replay dict shape."""
    return {"type": event.type, "seq": event.seq, "data": {"agent": event.data.get("agent"), **event.data}}
