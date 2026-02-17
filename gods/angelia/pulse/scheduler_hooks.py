"""Hooks shared between scheduler and runtime for inbox-event injection."""
from __future__ import annotations

from langchain_core.messages import SystemMessage

from gods.iris.service import fetch_inbox_context
from gods.angelia.pulse.policy import get_inject_budget, get_interrupt_mode


def inject_inbox_before_pulse(state: dict, project_id: str, agent_id: str):
    budget = get_inject_budget(project_id)
    text, ids = fetch_inbox_context(project_id, agent_id, budget)
    if not text:
        return
    state.setdefault("messages", [])
    state["messages"].append(SystemMessage(content=text, name="event_inbox"))
    state.setdefault("__inbox_delivered_ids", [])
    state["__inbox_delivered_ids"].extend(ids)


def inject_inbox_after_action_if_any(state: dict, project_id: str, agent_id: str) -> int:
    if get_interrupt_mode(project_id) != "after_action":
        return 0
    budget = get_inject_budget(project_id)
    text, ids = fetch_inbox_context(project_id, agent_id, budget)
    if not text:
        return 0
    state.setdefault("messages", [])
    state["messages"].append(SystemMessage(content=text, name="event_inbox"))
    state.setdefault("__inbox_delivered_ids", [])
    state["__inbox_delivered_ids"].extend(ids)
    return len(ids)
