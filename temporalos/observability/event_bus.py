"""In-process async pub/sub event bus.

Used to relay progress events, chat tokens, and copilot cues from the
background worker to any SSE consumer without requiring Redis or other
external message broker.

Topics are namespaced strings (e.g. ``job:{id}``, ``chat:{id}``, ``copilot:{id}``).
Subscribers get an ``asyncio.Queue`` and must drain it; the bus will drop
events for slow subscribers rather than block the publisher.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


class EventBus:
    """Topic-based async pub/sub. Thread-unsafe — use from a single event loop."""

    def __init__(self, max_queue: int = 256) -> None:
        self._subs: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._max_queue = max_queue

    def subscribe(self, topic: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subs[topic].add(q)
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue) -> None:
        if topic in self._subs:
            self._subs[topic].discard(q)
            if not self._subs[topic]:
                self._subs.pop(topic, None)

    def publish(self, topic: str, event: Dict[str, Any]) -> int:
        """Non-blocking publish. Returns number of subscribers the event reached."""
        queues = list(self._subs.get(topic, ()))
        delivered = 0
        for q in queues:
            try:
                q.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                logger.debug("Dropping event on full queue for topic=%s", topic)
        return delivered

    def subscriber_count(self, topic: str) -> int:
        return len(self._subs.get(topic, ()))


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
