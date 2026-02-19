"""Angelia wakeup bridge for event enqueue lifecycle.

Current policy: enqueue -> try wake immediately.
Future policy can evolve into enqueue -> decision -> wake.
"""
from __future__ import annotations

import threading

from gods import events as events_bus

_installed = False
_install_lock = threading.Lock()


def _extract_agent_id(record: events_bus.EventRecord) -> str:
    payload = dict(getattr(record, "payload", {}) or {})
    return str(payload.get("agent_id", "") or "").strip()


def _try_wake_on_enqueue(record: events_bus.EventRecord) -> None:
    aid = _extract_agent_id(record)
    if not aid:
        return
    try:
        from gods.angelia.scheduler import angelia_supervisor

        angelia_supervisor.wake_agent(record.project_id, aid)
    except Exception:
        return


def install_wakeup_bridge() -> None:
    global _installed
    if _installed:
        return
    with _install_lock:
        if _installed:
            return
        events_bus.register_enqueue_hook(_try_wake_on_enqueue)
        _installed = True
