"""
Agent scheduler for event-driven autonomous pulses.
"""
from __future__ import annotations

import random
import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple

from langchain_core.messages import HumanMessage

from gods.agents.base import GodAgent
from gods.config import runtime_config
from gods.prompts import prompt_registry

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
            }
            _AGENT_STATUS[key] = status
        return status


def has_pending_inbox(project_id: str, agent_id: str) -> bool:
    path = Path("projects") / project_id / "buffers" / f"{agent_id}.jsonl"
    if not path.exists():
        return False
    try:
        return path.stat().st_size > 0
    except Exception:
        return False


def _run_agent_until_pause(project_id: str, agent_id: str, reason: str) -> str:
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    pulse_message = prompt_registry.render("scheduler_pulse_message", project_id=project_id, reason=reason)
    pulse_context = prompt_registry.render("scheduler_pulse_context", project_id=project_id, reason=reason)
    state = {
        "project_id": project_id,
        "messages": [HumanMessage(content=pulse_message, name="system")],
        "context": pulse_context,
        "next_step": "",
    }
    state = agent.process(state)
    return state.get("next_step", "finish")


def pulse_agent_sync(project_id: str, agent_id: str, reason: str, force: bool = False) -> dict:
    status = _get_status(project_id, agent_id)
    lock = _get_lock(project_id, agent_id)
    now = time.time()

    if not lock.acquire(blocking=False):
        status["status"] = "running"
        return {"triggered": False, "reason": "busy"}

    try:
        if (not force) and now < float(status.get("next_eligible_at", 0.0)):
            status["status"] = "cooldown"
            return {"triggered": False, "reason": "cooldown"}

        status["status"] = "running"
        status["last_reason"] = reason
        status["last_error"] = ""
        status["last_pulse_at"] = now

        proj = runtime_config.projects.get(project_id)
        min_interval = int(getattr(proj, "simulation_interval_min", 10) if proj else 10)
        max_interval = int(getattr(proj, "simulation_interval_max", 40) if proj else 40)

        try:
            next_step = _run_agent_until_pause(project_id, agent_id, reason)
            status["last_next_step"] = next_step
        except Exception as e:
            status["status"] = "error"
            status["last_error"] = str(e)
            status["next_eligible_at"] = time.time() + max(10, min_interval)
            return {"triggered": False, "reason": f"error: {e}"}

        now2 = time.time()
        if next_step == "finish":
            # Empty/finished pulses are de-prioritized by exponential backoff.
            status["empty_cycles"] = int(status.get("empty_cycles", 0)) + 1
            backoff_factor = min(2 ** max(0, status["empty_cycles"] - 1), 8)
            cooldown = max(1, min_interval) * backoff_factor
            status["status"] = "idle"
            status["next_eligible_at"] = now2 + cooldown
        else:
            # Agent did real tool work in this pulse; keep it eligible but not spammed.
            status["empty_cycles"] = 0
            status["status"] = "idle"
            status["next_eligible_at"] = now2 + max(2, min_interval // 2)

        # Soft cap to avoid runaway delays.
        max_next = now2 + max(10, max_interval * 8)
        status["next_eligible_at"] = min(float(status["next_eligible_at"]), float(max_next))
        return {"triggered": True, "reason": reason, "next_step": next_step}
    finally:
        lock.release()


def get_project_status(project_id: str, active_agents: List[str]) -> List[dict]:
    result = []
    now = time.time()
    for agent_id in active_agents:
        st = dict(_get_status(project_id, agent_id))
        st["has_pending_inbox"] = has_pending_inbox(project_id, agent_id)
        st["now"] = now
        result.append(st)
    return result


def pick_pulse_batch(project_id: str, active_agents: List[str], batch_size: int) -> List[Tuple[str, str]]:
    now = time.time()
    urgent = []
    normal = []
    for agent_id in active_agents:
        st = _get_status(project_id, agent_id)
        eligible = now >= float(st.get("next_eligible_at", 0.0))
        if st.get("status") == "running":
            continue
        if has_pending_inbox(project_id, agent_id):
            urgent.append((agent_id, "inbox_event"))
        elif eligible:
            normal.append((agent_id, "heartbeat"))

    random.shuffle(urgent)
    random.shuffle(normal)
    merged = urgent + normal
    return merged[: max(1, batch_size)]
