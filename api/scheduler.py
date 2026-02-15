"""Agent scheduler for event-driven autonomous pulses."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Dict, List, Tuple

from langchain_core.messages import HumanMessage

from gods.agents.base import GodAgent
from gods.config import runtime_config
from gods.inbox import ack_handled, has_pending
from gods.prompts import prompt_registry
from gods.pulse import (
    PulseEventStatus,
    count_queued_events,
    enqueue_pulse_event,
    get_idle_heartbeat_sec,
    get_priority_weights,
    is_inbox_event_enabled,
    list_pulse_events,
    mark_pulse_event_done,
    pick_pulse_events,
)
from gods.pulse.scheduler_hooks import inject_inbox_before_pulse

_META_LOCK = threading.Lock()
_AGENT_LOCKS: Dict[Tuple[str, str], threading.Lock] = {}
_AGENT_STATUS: Dict[Tuple[str, str], dict] = {}


def _key(project_id: str, agent_id: str) -> Tuple[str, str]:
    return (project_id, agent_id)


def _get_lock(project_id: str, agent_id: str) -> threading.Lock:
    key = _key(project_id, agent_id)
    with _META_LOCK:
        lock = _AGENT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _AGENT_LOCKS[key] = lock
        return lock


def _get_status(project_id: str, agent_id: str) -> dict:
    key = _key(project_id, agent_id)
    with _META_LOCK:
        status = _AGENT_STATUS.get(key)
        if status is None:
            status = {
                "project_id": project_id,
                "agent_id": agent_id,
                "status": "idle",
                "last_reason": "",
                "last_pulse_at": 0.0,
                "next_eligible_at": 0.0,
                "empty_cycles": 0,
                "last_next_step": "",
                "last_error": "",
                "last_timer_emit_at": 0.0,
            }
            _AGENT_STATUS[key] = status
        return status


def has_pending_inbox(project_id: str, agent_id: str) -> bool:
    return has_pending(project_id, agent_id)


def _run_agent_until_pause(project_id: str, agent_id: str, reason: str, pulse_id: str) -> dict:
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    pulse_message = prompt_registry.render("scheduler_pulse_message", project_id=project_id, reason=reason)
    pulse_context = prompt_registry.render("scheduler_pulse_context", project_id=project_id, reason=reason)
    state = {
        "project_id": project_id,
        "messages": [HumanMessage(content=pulse_message, name="system")],
        "context": pulse_context,
        "next_step": "",
        "__pulse_meta": {
            "pulse_id": pulse_id,
            "reason": reason,
            "started_at": time.time(),
        },
    }
    inject_inbox_before_pulse(state, project_id=project_id, agent_id=agent_id)
    return agent.process(state)


def pulse_agent_sync(
    project_id: str,
    agent_id: str,
    reason: str,
    force: bool = False,
    pulse_event_id: str = "",
) -> dict:
    status = _get_status(project_id, agent_id)
    lock = _get_lock(project_id, agent_id)
    now = time.time()

    if not lock.acquire(blocking=False):
        status["status"] = "running"
        if pulse_event_id:
            mark_pulse_event_done(project_id, pulse_event_id, dropped=True)
        return {"triggered": False, "reason": "busy"}

    try:
        pulse_id = uuid.uuid4().hex[:12]
        if (not force) and now < float(status.get("next_eligible_at", 0.0)):
            status["status"] = "cooldown"
            if pulse_event_id:
                mark_pulse_event_done(project_id, pulse_event_id, dropped=True)
            return {"triggered": False, "reason": "cooldown", "pulse_id": pulse_id}

        status["status"] = "running"
        status["last_reason"] = reason
        status["last_error"] = ""
        status["last_pulse_at"] = now

        proj = runtime_config.projects.get(project_id)
        min_interval = int(getattr(proj, "simulation_interval_min", 10) if proj else 10)
        max_interval = int(getattr(proj, "simulation_interval_max", 40) if proj else 40)

        try:
            new_state = _run_agent_until_pause(project_id, agent_id, reason, pulse_id)
            next_step = str(new_state.get("next_step", "finish"))
            status["last_next_step"] = next_step
            delivered = list(new_state.get("__inbox_delivered_ids", []) or [])
            if delivered:
                ack_handled(project_id, delivered)
        except Exception as e:
            status["status"] = "error"
            status["last_error"] = str(e)
            status["next_eligible_at"] = time.time() + max(10, min_interval)
            if pulse_event_id:
                mark_pulse_event_done(project_id, pulse_event_id, dropped=True)
            return {"triggered": False, "reason": f"error: {e}", "pulse_id": pulse_id}

        now2 = time.time()
        if next_step == "finish":
            status["empty_cycles"] = int(status.get("empty_cycles", 0)) + 1
            backoff_factor = min(2 ** max(0, status["empty_cycles"] - 1), 8)
            cooldown = max(1, min_interval) * backoff_factor
            status["status"] = "idle"
            status["next_eligible_at"] = now2 + cooldown
        else:
            status["empty_cycles"] = 0
            status["status"] = "idle"
            status["next_eligible_at"] = now2 + max(2, min_interval // 2)

        max_next = now2 + max(10, max_interval * 8)
        status["next_eligible_at"] = min(float(status["next_eligible_at"]), float(max_next))
        if pulse_event_id:
            mark_pulse_event_done(project_id, pulse_event_id, dropped=False)
        return {"triggered": True, "reason": reason, "next_step": next_step, "pulse_id": pulse_id}
    finally:
        lock.release()


def get_project_status(project_id: str, active_agents: List[str]) -> List[dict]:
    result = []
    now = time.time()
    for agent_id in active_agents:
        st = dict(_get_status(project_id, agent_id))
        st["has_pending_inbox"] = has_pending_inbox(project_id, agent_id)
        st["queued_pulse_events"] = len(
            list_pulse_events(project_id, agent_id=agent_id, status=PulseEventStatus.QUEUED, limit=200)
        )
        st["now"] = now
        result.append(st)
    return result


def _enqueue_idle_timer_events(project_id: str, active_agents: List[str], now: float):
    idle_sec = get_idle_heartbeat_sec(project_id)
    weights = get_priority_weights(project_id)
    timer_priority = int(weights.get("timer", 10))

    for agent_id in active_agents:
        st = _get_status(project_id, agent_id)
        if st.get("status") == "running":
            continue
        eligible = now >= float(st.get("next_eligible_at", 0.0))
        if not eligible:
            continue
        last_emit = float(st.get("last_timer_emit_at", 0.0) or 0.0)
        if now - last_emit < idle_sec:
            continue
        enqueue_pulse_event(
            project_id=project_id,
            agent_id=agent_id,
            event_type="timer",
            priority=timer_priority,
            payload={"reason": "idle_heartbeat"},
        )
        st["last_timer_emit_at"] = now


def pick_pulse_batch(project_id: str, active_agents: List[str], batch_size: int) -> List[Tuple[str, str, str]]:
    if not active_agents:
        return []

    now = time.time()
    queued = count_queued_events(project_id, active_agents)
    if queued <= 0:
        _enqueue_idle_timer_events(project_id, active_agents, now)

    picked = pick_pulse_events(project_id, active_agents, batch_size=max(1, int(batch_size)))
    out: List[Tuple[str, str, str]] = []
    for item in picked:
        reason = item.event_type
        if item.event_type == "timer" and isinstance(item.payload, dict) and item.payload.get("reason"):
            reason = str(item.payload.get("reason"))
        out.append((item.agent_id, reason, item.event_id))
    return out


def push_manual_pulse(project_id: str, agent_id: str, event_type: str = "manual", payload: dict | None = None) -> dict:
    weights = get_priority_weights(project_id)
    priority = int(weights.get(event_type, weights.get("manual", 80)))
    event = enqueue_pulse_event(
        project_id=project_id,
        agent_id=agent_id,
        event_type=event_type,
        priority=priority,
        payload=payload or {},
    )
    return event.to_dict()
