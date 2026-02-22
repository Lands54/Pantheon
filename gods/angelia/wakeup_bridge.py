"""Angelia wakeup bridge for event enqueue lifecycle.

Current policy: enqueue -> try wake immediately.
Future policy can evolve into enqueue -> decision -> wake.
"""
from __future__ import annotations

import threading

from gods import events as events_bus
from gods.config import runtime_config
from gods.identity import is_valid_agent_id

_installed = False
_install_lock = threading.Lock()


def _extract_agent_id(record: events_bus.EventRecord) -> str:
    payload = dict(getattr(record, "payload", {}) or {})
    return str(payload.get("agent_id", "") or "").strip()


def _try_wake_on_enqueue(record: events_bus.EventRecord) -> None:
    # Interaction events are synchronous routing-layer events and should
    # not participate in Angelia wake semantics.
    if str(getattr(record, "domain", "") or "").strip() == "interaction":
        return
    aid = _extract_agent_id(record)
    if not aid:
        return
    if not is_valid_agent_id(aid):
        return
    proj = runtime_config.projects.get(record.project_id)
    if not proj:
        return
    if aid not in set(getattr(proj, "active_agents", []) or []):
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
