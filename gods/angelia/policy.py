"""Angelia policy helpers."""
from __future__ import annotations

from gods.config import runtime_config


_DEFAULT_WEIGHTS = {
    "mail_event": 100,
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
    v = int(getattr(proj, "angelia_timer_idle_sec", 60) if proj else 60)
    return max(5, min(v, 3600))


def timer_enabled(project_id: str) -> bool:
    proj = _project(project_id)
    return bool(getattr(proj, "angelia_timer_enabled", True) if proj else True)


def cooldown_preempt_types(project_id: str) -> set[str]:
    proj = _project(project_id)
    raw = (
        getattr(
            proj,
            "angelia_cooldown_preempt_types",
            ["mail_event", "manual", "detach_failed_event", "detach_lost_event"],
        )
        if proj
        else ["mail_event", "manual", "detach_failed_event", "detach_lost_event"]
    )
    out = {str(x).strip() for x in (raw or []) if str(x).strip()}
    if not out:
        out = {"mail_event", "manual", "detach_failed_event", "detach_lost_event"}
    return out


def force_pick_after_sec(project_id: str) -> int:
    """
    Anti-starvation SLA:
    if one queued event waits too long, allow it to pass cooldown gate.
    """
    proj = _project(project_id)
    min_interval = int(getattr(proj, "simulation_interval_min", 10) if proj else 10)
    max_interval = int(getattr(proj, "simulation_interval_max", 40) if proj else 40)
    # Mature but simple heuristic: ~3 cycles or 30s minimum.
    v = max(30, max(min_interval * 3, max_interval * 3))
    return min(v, 600)


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


def finalize_quiescent_enabled(project_id: str) -> bool:
    proj = _project(project_id)
    return bool(getattr(proj, "finalize_quiescent_enabled", True) if proj else True)


def finalize_sleep_bounds(project_id: str) -> tuple[int, int, int]:
    proj = _project(project_id)
    min_sec = int(getattr(proj, "finalize_sleep_min_sec", 15) if proj else 15)
    default_sec = int(getattr(proj, "finalize_sleep_default_sec", 120) if proj else 120)
    max_sec = int(getattr(proj, "finalize_sleep_max_sec", 1800) if proj else 1800)
    min_sec = max(5, min(min_sec, 3600))
    max_sec = max(min_sec, min(max_sec, 24 * 3600))
    default_sec = max(min_sec, min(default_sec, max_sec))
    return min_sec, default_sec, max_sec


def finalize_sleep_sec(project_id: str, requested: int | None) -> int:
    min_sec, default_sec, max_sec = finalize_sleep_bounds(project_id)
    if requested is None:
        return default_sec
    try:
        val = int(requested)
    except Exception:
        return default_sec
    if val <= 0:
        return default_sec
    return max(min_sec, min(val, max_sec))
