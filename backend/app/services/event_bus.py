"""In-process async pub/sub event bus backing SSE and WebSocket streams."""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Set


@dataclass(slots=True)
class BusEvent:
    """A single published event."""

    topic: str
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription:
    """Async-iterator handle over one subscriber's bounded queue."""

    def __init__(self, topic: str, queue: asyncio.Queue[BusEvent]) -> None:
        self.topic = topic
        self._queue = queue
        self._closed = False

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    async def next_event(self, timeout: float | None = None) -> BusEvent | None:
        """Await the next event; ``None`` on timeout or after close."""
        if timeout is None:
            if self._closed and self._queue.empty():
                return None
            return await self._queue.get()
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def __aiter__(self) -> AsyncIterator[BusEvent]:
        return self

    async def __anext__(self) -> BusEvent:
        event = await self.next_event()
        if event is None:
            raise StopAsyncIteration
        return event


class EventBus:
    """Topic-based fan-out bus with bounded, drop-oldest subscriber queues."""

    def __init__(self, max_queue: int = 2000) -> None:
        self._max_queue = max_queue
        self._subscribers: dict[str, Set[asyncio.Queue[BusEvent]]] = defaultdict(set)
        self._seq = 0
        self._lock = asyncio.Lock()

    def subscribe(self, topic: str) -> Subscription:
        """Register a new subscriber on ``topic``."""
        queue: asyncio.Queue[BusEvent] = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers[topic].add(queue)
        return Subscription(topic, queue)

    def unsubscribe(self, subscription: Subscription) -> None:
        """Drop a subscriber (idempotent)."""
        with contextlib.suppress(KeyError):
            self._subscribers[subscription.topic].discard(subscription._queue)  # noqa: SLF001

    async def publish(self, topic: str, type_: str, data: dict[str, Any] | None = None) -> BusEvent:
        """Fan an event out to every subscriber of ``topic`` (drop-oldest)."""
        self._seq += 1
        event = BusEvent(topic=topic, type=type_, data=data or {}, seq=self._seq)
        for queue in list(self._subscribers.get(topic, ())):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()  # drop oldest to keep the stream live
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)
        return event

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, ()))
