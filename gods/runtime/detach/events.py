"""Detach domain event emission helpers for unified event bus."""
from __future__ import annotations

from typing import Any

from gods import events as events_bus


def emit_detach_event(
    project_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    priority: int = 35,
    dedupe_key: str = "",
    meta: dict[str, Any] | None = None,
):
    rec = events_bus.EventRecord.create(
        project_id=project_id,
        domain="runtime",
        event_type=event_type,
        priority=priority,
        payload=payload or {},
        dedupe_key=dedupe_key,
        max_attempts=3,
        meta=meta or {"source": "detach"},
    )
    events_bus.append_event(rec)

