"""In-process Hermes event bus for monitoring and SSE."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any


class HermesEventBus:
    def __init__(self, max_events: int = 5000):
        self._lock = threading.Lock()
        self._events = deque(maxlen=max_events)
        self._seq = 0

    def publish(self, event_type: str, project_id: str, payload: dict[str, Any]) -> dict:
        with self._lock:
            self._seq += 1
            event = {
                "seq": self._seq,
                "timestamp": time.time(),
                "type": event_type,
                "project_id": project_id,
                "payload": payload,
            }
            self._events.append(event)
            return event

    def get_since(self, last_seq: int, project_id: str | None = None, limit: int = 200) -> list[dict]:
        with self._lock:
            out = []
            for event in self._events:
                if event["seq"] <= last_seq:
                    continue
                if project_id and event.get("project_id") != project_id:
                    continue
                out.append(event)
                if len(out) >= limit:
                    break
            return out


hermes_events = HermesEventBus()
