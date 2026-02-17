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
    aid = str((payload or {}).get("agent_id", "")).strip()
    if not aid:
        return
    title_map = {
        "detach_submitted_event": "Detach Submitted",
        "detach_started_event": "Detach Started",
        "detach_stopping_event": "Detach Stopping",
        "detach_stopped_event": "Detach Stopped",
        "detach_failed_event": "Detach Failed",
        "detach_reconciled_event": "Detach Reconciled",
        "detach_lost_event": "Detach Lost",
    }
    if event_type not in title_map:
        return
    try:
        from gods.interaction import facade as interaction_facade
        content = f"{event_type}: {payload or {}}"
        interaction_facade.submit_detach_notice(
            project_id=project_id,
            agent_id=aid,
            title=title_map[event_type],
            content=content,
            msg_type="detach_notice",
            trigger_pulse=True,
            priority=priority,
            dedupe_key=f"interaction_{dedupe_key or event_type}",
        )
    except Exception:
        pass
