"""Policy helpers for pulse queue scheduling and injection."""
from __future__ import annotations

from gods.config import runtime_config


_DEFAULT_WEIGHTS = {
    "inbox_event": 100,
    "manual": 80,
    "system": 60,
    "timer": 10,
}


def get_idle_heartbeat_sec(project_id: str) -> int:
    proj = runtime_config.projects.get(project_id)
    value = int(getattr(proj, "queue_idle_heartbeat_sec", 60) if proj else 60)
    return max(5, min(value, 3600))


def get_inject_budget(project_id: str) -> int:
    proj = runtime_config.projects.get(project_id)
    value = int(getattr(proj, "pulse_event_inject_budget", 3) if proj else 3)
    return max(1, min(value, 32))


def get_interrupt_mode(project_id: str) -> str:
    proj = runtime_config.projects.get(project_id)
    mode = str(getattr(proj, "pulse_interrupt_mode", "after_action") if proj else "after_action")
    if mode != "after_action":
        return "after_action"
    return mode


def get_priority_weights(project_id: str) -> dict[str, int]:
    proj = runtime_config.projects.get(project_id)
    raw = getattr(proj, "pulse_priority_weights", None) if proj else None
    out = dict(_DEFAULT_WEIGHTS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                out[str(k)] = int(v)
            except Exception:
                continue
    return out


def is_inbox_event_enabled(project_id: str) -> bool:
    proj = runtime_config.projects.get(project_id)
    return bool(getattr(proj, "inbox_event_enabled", True) if proj else True)
