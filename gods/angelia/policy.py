"""Angelia policy helpers."""
from __future__ import annotations

from gods.config import runtime_config


_DEFAULT_WEIGHTS = {
    "inbox_event": 100,
    "manual": 80,
    "system": 60,
    "timer": 10,
}


def _project(project_id: str):
    return runtime_config.projects.get(project_id)


def event_max_attempts(project_id: str) -> int:
    proj = _project(project_id)
    v = int(getattr(proj, "angelia_event_max_attempts", 3) if proj else 3)
    return max(1, min(v, 20))


def processing_timeout_sec(project_id: str) -> int:
    proj = _project(project_id)
    v = int(getattr(proj, "angelia_processing_timeout_sec", 60) if proj else 60)
    return max(5, min(v, 3600))


def dedupe_window_sec(project_id: str) -> int:
    proj = _project(project_id)
    v = int(getattr(proj, "angelia_dedupe_window_sec", 5) if proj else 5)
    return max(0, min(v, 300))


def timer_idle_sec(project_id: str) -> int:
    proj = _project(project_id)
    legacy = int(getattr(proj, "queue_idle_heartbeat_sec", 60) if proj else 60)
    v = int(getattr(proj, "angelia_timer_idle_sec", legacy) if proj else legacy)
    return max(5, min(v, 3600))


def timer_enabled(project_id: str) -> bool:
    proj = _project(project_id)
    return bool(getattr(proj, "angelia_timer_enabled", True) if proj else True)


def cooldown_preempt_types(project_id: str) -> set[str]:
    proj = _project(project_id)
    raw = getattr(proj, "angelia_cooldown_preempt_types", ["inbox_event", "manual"]) if proj else ["inbox_event", "manual"]
    out = {str(x).strip() for x in (raw or []) if str(x).strip()}
    if not out:
        out = {"inbox_event", "manual"}
    return out


def priority_weights(project_id: str) -> dict[str, int]:
    proj = _project(project_id)
    raw = getattr(proj, "pulse_priority_weights", None) if proj else None
    out = dict(_DEFAULT_WEIGHTS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                out[str(k)] = int(v)
            except Exception:
                continue
    return out


def default_priority(project_id: str, event_type: str) -> int:
    w = priority_weights(project_id)
    et = str(event_type or "system")
    return int(w.get(et, w.get("system", 60)))


def cooldown_from_next_step(project_id: str, next_step: str, empty_cycles: int) -> int:
    proj = _project(project_id)
    min_interval = int(getattr(proj, "simulation_interval_min", 10) if proj else 10)
    max_interval = int(getattr(proj, "simulation_interval_max", 40) if proj else 40)
    if next_step == "finish":
        backoff_factor = min(2 ** max(0, int(empty_cycles) - 1), 8)
        cooldown = max(1, min_interval) * backoff_factor
    else:
        cooldown = max(2, min_interval // 2)
    max_next = max(10, max_interval * 8)
    return min(int(cooldown), int(max_next))
