"""Public facade for angelia domain operations."""
from __future__ import annotations

from typing import Any

from gods.angelia import store
from gods.angelia.metrics import angelia_metrics
from gods.angelia.models import AngeliaEventState
from gods.angelia.scheduler import angelia_supervisor
from gods.angelia.wakeup_bridge import install_wakeup_bridge
from gods.angelia.pulse.policy import (
    get_inject_budget,
    get_interrupt_mode,
    get_priority_weights,
    is_mail_event_wakeup_enabled,
)
from gods.angelia.pulse.scheduler_hooks import (
    inject_inbox_after_action_if_any,
    inject_inbox_before_pulse,
)


def enqueue_event(
    project_id: str,
    agent_id: str,
    event_type: str,
    payload: dict | None = None,
    priority: int | None = None,
    dedupe_key: str = "",
) -> dict[str, Any]:
    return angelia_supervisor.enqueue_event(
        project_id=project_id,
        agent_id=agent_id,
        event_type=event_type,
        payload=payload or {},
        priority=priority,
        dedupe_key=dedupe_key,
    )


def list_events(
    project_id: str,
    agent_id: str = "",
    state: str = "",
    event_type: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    st = AngeliaEventState(state) if state else None
    rows = store.list_events(
        project_id=project_id,
        agent_id=agent_id,
        state=st,
        event_type=event_type,
        limit=max(1, min(limit, 1000)),
    )
    return [r.to_dict() for r in rows]


def retry_event(project_id: str, event_id: str) -> bool:
    return bool(store.retry_event(project_id, event_id))


def list_agent_status(project_id: str, active_agents: list[str]) -> list[dict[str, Any]]:
    return angelia_supervisor.list_agent_status(project_id, active_agents)


def wake_agent(project_id: str, agent_id: str) -> dict[str, Any]:
    return angelia_supervisor.wake_agent(project_id, agent_id)


def tick_timer_once(project_id: str) -> dict[str, Any]:
    return angelia_supervisor.tick_timer_once(project_id)


def metrics_snapshot() -> dict[str, Any]:
    return angelia_metrics.snapshot()


def start_supervisor():
    angelia_supervisor.start()


def stop_supervisor():
    angelia_supervisor.stop()


def stop_project_workers(project_id: str):
    angelia_supervisor.stop_project_workers(project_id)


def install_event_enqueue_wakeup_bridge() -> None:
    install_wakeup_bridge()


__all__ = [
    "enqueue_event",
    "list_events",
    "retry_event",
    "list_agent_status",
    "wake_agent",
    "tick_timer_once",
    "metrics_snapshot",
    "start_supervisor",
    "stop_supervisor",
    "stop_project_workers",
    "install_event_enqueue_wakeup_bridge",
    "get_priority_weights",
    "is_mail_event_wakeup_enabled",
    "get_inject_budget",
    "get_interrupt_mode",
    "inject_inbox_before_pulse",
    "inject_inbox_after_action_if_any",
    "angelia_supervisor",
]
