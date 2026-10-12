"""Real-time updates over WebSockets.

One connection per open page: /ws/courses/{course_id}. Messages are JSON:

  {"type": "poll_opened",  "poll": {...}}          everyone in the course
  {"type": "poll_closed",  "poll_id": 7}           everyone in the course
  {"type": "results",      "results": {...}}       instructors (students too if show_results)

Everything lives in this one process, which matches the deployment plan
(one backend container with SQLite). Request handlers run in worker
threads, so publish() hands messages to the event loop thread-safely, and
only after the request's transaction has committed (see deps.get_db).
"""
from __future__ import annotations

import asyncio
import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=False)
class Listener:
    user_id: int
    is_instructor: bool
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))
    loop: asyncio.AbstractEventLoop = field(default_factory=asyncio.get_running_loop)

    def deliver(self, text: str) -> None:
        try:
            self.queue.put_nowait(text)
        except asyncio.QueueFull:  # a stuck client: drop the message rather than slow everyone down
            pass


class Hub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.listeners: dict[int, set[Listener]] = defaultdict(set)

    def add(self, course_id: int, listener: Listener) -> None:
        with self._lock:
            self.listeners[course_id].add(listener)

    def remove(self, course_id: int, listener: Listener) -> None:
        with self._lock:
            self.listeners[course_id].discard(listener)
            if not self.listeners[course_id]:
                self.listeners.pop(course_id, None)

    def count(self, course_id: int) -> int:
        with self._lock:
            return len(self.listeners.get(course_id, ()))

    def publish(self, course_id: int, message: dict[str, Any], *, instructors_only: bool = False) -> None:
        """Safe to call from any thread (request handlers run in worker threads)."""
        text = json.dumps(message, default=str)
        with self._lock:
            targets = [l for l in self.listeners.get(course_id, ()) if l.is_instructor or not instructors_only]
        for listener in targets:
            if not listener.loop.is_closed():
                listener.loop.call_soon_threadsafe(listener.deliver, text)


hub = Hub()
