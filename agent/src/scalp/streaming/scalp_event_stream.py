"""SSE Stream publisher for real-time scalp session event streaming to frontend clients."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Set

logger = logging.getLogger(__name__)


class ScalpEventBroadcaster:
    def __init__(self) -> None:
        self._listeners: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        if session_id not in self._listeners:
            self._listeners[session_id] = set()
        queue: asyncio.Queue = asyncio.Queue()
        self._listeners[session_id].add(queue)
        logger.info(f"New client subscribed to SSE events for session {session_id}")
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        if session_id in self._listeners:
            self._listeners[session_id].discard(queue)
            if not self._listeners[session_id]:
                del self._listeners[session_id]

    async def broadcast(self, session_id: str, event_type: str, payload: Dict) -> None:
        listeners = list(self._listeners.get(session_id, []))
        if not listeners:
            return

        msg = {
            "event": event_type,
            "data": payload,
        }
        for q in listeners:
            try:
                await q.put(msg)
            except Exception:
                pass


_event_broadcaster_instance: ScalpEventBroadcaster | None = None


def get_event_broadcaster() -> ScalpEventBroadcaster:
    global _event_broadcaster_instance
    if _event_broadcaster_instance is None:
        _event_broadcaster_instance = ScalpEventBroadcaster()
    return _event_broadcaster_instance


async def scalp_event_generator(session_id: str) -> AsyncGenerator[str, None]:
    broadcaster = get_event_broadcaster()
    queue = broadcaster.subscribe(session_id)

    # Initial snapshot event
    init_data = json.dumps({"session_id": session_id, "status": "connected"})
    yield f"event: session.snapshot\ndata: {init_data}\n\n"

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15.0)
                event_name = item.get("event", "message")
                data_str = json.dumps(item.get("data", {}))
                yield f"event: {event_name}\ndata: {data_str}\n\n"
            except asyncio.TimeoutError:
                # Keep-alive heartbeat every 15s
                yield ": heartbeat\n\n"
    except asyncio.CancelledError:
        broadcaster.unsubscribe(session_id, queue)
        logger.info(f"SSE client disconnected from session {session_id}")
