"""In-process per-user SSE activity hub (single-worker safe).

Publish is safe from the Uvicorn event loop and from automation worker
threads that run a separate asyncio.run() loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class UserActivityHub:
    """Publish activity events to subscribers for a given user_id."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
        self._async_lock = asyncio.Lock()
        self._thread_lock = threading.RLock()
        self._main_loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Remember the Uvicorn/request loop for cross-thread publish."""
        try:
            self._main_loop = loop or asyncio.get_running_loop()
        except RuntimeError:
            pass

    def _queues_for(self, user_id: str) -> list[asyncio.Queue[dict[str, Any]]]:
        with self._thread_lock:
            return list(self._subscribers.get(user_id) or [])

    async def subscribe(self, user_id: str) -> asyncio.Queue[dict[str, Any]]:
        self.bind_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        async with self._async_lock:
            with self._thread_lock:
                self._subscribers[user_id].append(queue)
        return queue

    async def unsubscribe(self, user_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._async_lock:
            with self._thread_lock:
                subs = self._subscribers.get(user_id) or []
                if queue in subs:
                    subs.remove(queue)
                if not subs and user_id in self._subscribers:
                    del self._subscribers[user_id]

    def _enqueue(self, queue: asyncio.Queue[dict[str, Any]], event: dict[str, Any]) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                _ = queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def _deliver(self, user_id: str, event: dict[str, Any]) -> None:
        for queue in self._queues_for(user_id):
            self._enqueue(queue, event)

    async def publish(self, user_id: str, event: dict[str, Any]) -> None:
        """Publish on the current event loop (Uvicorn / request handlers)."""
        self.bind_loop()
        self._deliver(user_id, event)

    def publish_threadsafe(self, user_id: str, event: dict[str, Any]) -> None:
        """Publish from any thread onto the main (SSE) event loop."""
        loop = self._main_loop
        if loop is None or not loop.is_running():
            # No SSE subscribers yet — drop quietly (DB row still persisted)
            logger.debug("activity hub: no main loop for threadsafe publish")
            return

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is loop:
            self._deliver(user_id, event)
            return

        try:
            loop.call_soon_threadsafe(self._deliver, user_id, event)
        except RuntimeError as exc:
            logger.debug("activity hub publish_threadsafe failed: %s", exc)


activity_hub = UserActivityHub()
