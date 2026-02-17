"""In-process Hermes event bus for monitoring and SSE."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from gods import events as events_bus


_TYPE_MAP = {
    "protocol_invoked": "hermes_protocol_invoked_event",
    "protocol_registered": "hermes_contract_registered_event",
    "job_updated": "hermes_job_updated_event",
    "contract_registered": "hermes_contract_registered_event",
    "contract_committed": "hermes_contract_committed_event",
    "contract_disable_requested": "hermes_contract_disabled_event",
    "contract_disabled": "hermes_contract_disabled_event",
}


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
            bus_type = _TYPE_MAP.get(str(event_type or "").strip(), "")
            if bus_type and project_id:
                try:
                    rec = events_bus.EventRecord.create(
                        project_id=project_id,
                        domain="hermes",
                        event_type=bus_type,
                        priority=40,
                        payload=payload or {},
                        dedupe_key="",
                        max_attempts=3,
                        meta={"source": "hermes_event_bus", "legacy_type": event_type},
                    )
                    events_bus.append_event(rec)
                except Exception:
                    # Hermes in-process observers should not fail due to persistence side effects.
                    pass
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
