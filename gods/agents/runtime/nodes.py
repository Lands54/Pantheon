"""Reusable LangGraph nodes for agent runtime."""
from __future__ import annotations

import time
import uuid
from typing import Any

from langchain_core.messages import ToolMessage

from gods.angelia.facade import inject_inbox_after_action_if_any
from gods.janus import ContextBuildRequest, janus_service
from gods.mnemosyne.intent_builders import (
    intent_from_agent_marker,
    intent_from_llm_response,
)

from .models import RuntimeState


def build_context_node(agent, state: RuntimeState) -> RuntimeState:
    inbox_hint = agent._build_inbox_context_hint()
    req = ContextBuildRequest(
        project_id=agent.project_id,
        agent_id=agent.agent_id,
        state=state,
        directives=agent._build_behavior_directives(),
        local_memory=agent._load_local_memory(),
        inbox_hint=inbox_hint,
        phase_name=str(state.get("strategy", "react_graph")),
        phase_block="",
        tools_desc=agent._render_tools_desc(),
    )
    llm_messages, _ = janus_service.build_llm_messages(req)
    state["llm_messages_buffer"] = list(llm_messages)
    return state


def llm_think_node(agent, state: RuntimeState) -> RuntimeState:
    llm_messages = list(state.get("llm_messages_buffer", []) or [])
    response = agent.brain.think_with_tools(
        llm_messages,
        agent.get_tools(),
        trace_meta=state.get("pulse_meta", {}) if isinstance(state, dict) else {},
    )
    state.setdefault("messages", []).append(response)
    content_text = response.content or "[No textual response]"
    if not agent._is_transient_llm_error_text(content_text):
        agent._record_intent(
            intent_from_llm_response(
                project_id=agent.project_id,
                agent_id=agent.agent_id,
                phase=str(state.get("strategy", "react_graph")),
                content=content_text,
            )
        )
    state["tool_calls"] = list(getattr(response, "tool_calls", []) or [])
    return state


def dispatch_tools_node(agent, state: RuntimeState) -> RuntimeState:
    calls = list(state.get("tool_calls", []) or [])
    results: list[str] = []
    for call in calls:
        tool_name = str(call.get("name", "") or "")
        args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
        tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"
        obs = agent.execute_tool(tool_name, args)
        results.append(str(obs))
        state.setdefault("messages", []).append(
            ToolMessage(content=str(obs), tool_call_id=tool_call_id, name=tool_name)
        )
        if tool_name == "post_to_synod":
            state["next_step"] = "escalated"
            break
        if tool_name == "abstain_from_synod":
            abstained = list(state.get("abstained", []) or [])
            if agent.agent_id not in abstained:
                abstained.append(agent.agent_id)
            state["abstained"] = abstained
            state["next_step"] = "abstained"
            break
        if tool_name == "finalize":
            state["finalize_control"] = agent._finalize_control_from_args(args)
            state["next_step"] = "finish"
            break
        injected = inject_inbox_after_action_if_any(state, agent.project_id, agent.agent_id)
        if injected > 0:
            agent._record_intent(
                intent_from_agent_marker(
                    project_id=agent.project_id,
                    agent_id=agent.agent_id,
                    marker="event_injected",
                    payload={"count": int(injected)},
                )
            )
    state["tool_results"] = results
    return state


def decide_next_node(agent, state: RuntimeState) -> RuntimeState:
    step = str(state.get("next_step", "") or "")
    if step in {"finish", "escalated", "abstained", "continue"}:
        state["route"] = "done"
        return state

    calls = list(state.get("tool_calls", []) or [])
    if not calls:
        state["next_step"] = "finish"
        state["route"] = "done"
        return state

    loop_count = int(state.get("loop_count", 0) or 0) + 1
    state["loop_count"] = loop_count
    max_rounds = int(state.get("max_rounds", 8) or 8)
    if loop_count >= max_rounds:
        agent._record_intent(
            intent_from_agent_marker(
                project_id=agent.project_id,
                agent_id=agent.agent_id,
                marker="tool_loop_cap",
                payload={"project_id": agent.project_id, "agent_id": agent.agent_id, "max_rounds": max_rounds},
            )
        )
        state["next_step"] = "continue"
        state["route"] = "done"
        return state

    state["next_step"] = ""
    state["route"] = "again"
    return state


def on_runtime_error(agent, state: RuntimeState, err: Exception) -> RuntimeState:
    msg = (
        f"Agent Runtime Error: {type(err).__name__}: {err}\n"
        "Suggested next step: check latest event payload/tool output and retry."
    )
    state.setdefault("messages", []).append(ToolMessage(content=msg, tool_call_id=f"runtime_err_{int(time.time())}", name="runtime"))
    state["next_step"] = "continue"
    return state
