"""
Phase-based autonomous runtime for GodAgent.
New deterministic cycle:
Reason -> Action (batch tool calls) -> Observe (finalize decision)
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from gods.config import runtime_config
from gods.prompts import prompt_registry
from gods.agents.tool_policy import SOCIAL_TOOLS, get_disabled_tools
from gods.agents.debug_trace import PulseTraceLogger
from gods.agents.runtime_policy import resolve_phase_strategy
from gods.pulse.scheduler_hooks import inject_inbox_after_action_if_any
from gods.janus import janus_service, ContextBuildRequest
from gods.agents.phase_runtime.policy import (
    AgentPhase,
    PhaseToolPolicy,
    PRODUCTIVE_ACT_TOOLS,
    base_phases,
    phase_names,
)
from gods.agents.phase_runtime.strategies import (
    PHASE_STRATEGY_STRICT_TRIAD,
    PHASE_STRATEGY_ITERATIVE_ACTION,
    PHASE_STRATEGIES,
)


class AgentPhaseRuntime:
    """
    Deterministic 3-stage runtime for executing agent pulses in a structured manner.
    The cycle typically consists of Reason, Act, and Observe phases.
    """
    def __init__(self, agent):
        """
        Initializes the phase runtime for a specific agent.
        """
        self.agent = agent
        self._state_path = self.agent.agent_dir / "runtime_state.json"

    def _project_cfg(self):
        """
        Retrieves the project configuration for the agent's current project.
        """
        return runtime_config.projects.get(self.agent.project_id)

    def _disabled_tools(self) -> set:
        """
        Returns the set of tools disabled for the agent.
        """
        return get_disabled_tools(self.agent.project_id, self.agent.agent_id)

    def _build_phase_allow_map(self, phases: List[AgentPhase]) -> Dict[str, set]:
        """
        Constructs a mapping of phase names to their corresponding allowed tool sets.
        """
        disabled = self._disabled_tools()
        allow_map: Dict[str, set] = {}
        for phase in phases:
            allow = set(phase.allowed_tools)
            if (SOCIAL_TOOLS & disabled) == SOCIAL_TOOLS:
                allow -= SOCIAL_TOOLS
            allow_map[phase.name] = allow
        return allow_map

    def _save_runtime_state(self, phase_idx: int, no_progress_rounds: int):
        """
        Persists the current runtime state index to allow for deterministic resumption.
        """
        # Persist runtime cursor between pulses so scheduler wakeups can resume deterministically.
        payload = {
            "phase_idx": int(max(0, phase_idx)),
            "no_progress_rounds": int(max(0, no_progress_rounds)),
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _phase_prompt(self, phase: AgentPhase, phase_order: List[str]) -> str:
        """
        Renders the specific prompt block for a given agent phase.
        """
        return prompt_registry.render(
            phase.prompt_template,
            project_id=self.agent.project_id,
            phase_name=phase.name,
            phase_order=" -> ".join(phase_order),
            allowed_tools=", ".join(phase.allowed_tools),
        )

    def _append_memory(self, text: str, record_type: str = "llm.response", payload: dict | None = None):
        """Compatibility wrapper for old test doubles using _append_to_memory(text) signature."""
        fn = getattr(self.agent, "_append_to_memory")
        try:
            fn(text, record_type=record_type, payload=payload or {})
        except TypeError:
            fn(text)

    def _finish(self, state):
        """
        Sets the state to finish and resets the runtime persistence.
        """
        state["next_step"] = "finish"
        self._save_runtime_state(0, 0)
        return state

    def _continue(self, state):
        """
        Sets the state to continue and resets the runtime persistence.
        """
        state["next_step"] = "continue"
        self._save_runtime_state(0, 0)
        return state

    def _think(self, state, phase, phase_order, simulation_directives, local_memory, inbox_msgs, pulse_meta):
        """
        Executes a single inference step within a specific phase.
        """
        # Keep one shared context model while swapping phase-specific prompt blocks.
        phase_block = self._phase_prompt(phase, phase_order)
        if hasattr(self.agent, "_render_tools_desc"):
            tools_desc = self.agent._render_tools_desc()
        else:
            tools_desc = "\n".join(
                [f"- [[{t.name}({', '.join(getattr(t, 'args', []))})]]: {getattr(t, 'description', '')}" for t in self.agent.get_tools()]
            )
        req = ContextBuildRequest(
            project_id=self.agent.project_id,
            agent_id=self.agent.agent_id,
            state=state,
            directives=simulation_directives,
            local_memory=local_memory,
            inbox_hint=inbox_msgs,
            phase_block=phase_block,
            phase_name=phase.name,
            tools_desc=tools_desc,
        )
        llm_messages, _ = janus_service.build_llm_messages(req)
        response: AIMessage = self.agent.brain.think_with_tools(
            llm_messages,
            self.agent.get_tools(),
            trace_meta=pulse_meta,
        )
        state["messages"].append(response)
        self._append_memory(
            response.content or "[No textual response]",
            record_type="llm.response",
            payload={"phase": phase.name, "content": response.content or "[No textual response]"},
        )
        return response

    def _violation_feedback(self, phase_name: str) -> str:
        """
        Provides feedback messages when an agent violates phase-specific tool constraints.
        """
        if phase_name == "reason":
            return (
                "RULE VIOLATION: Reason phase is planning-only. "
                "Do NOT call any tool. Reply again with plain text plan only."
            )
        if phase_name == "observe":
            return (
                "RULE VIOLATION: Observe phase allows ONLY `finalize` tool. "
                "If complete call finalize, otherwise reply with plain text status and no tools."
            )
        return "RULE VIOLATION: Retry with valid output for current phase."

    def _strategy_name(self) -> str:
        """
        Resolves the configured phase strategy name for the current project.
        """
        name = resolve_phase_strategy(self.agent.project_id, self.agent.agent_id)
        if name not in PHASE_STRATEGIES:
            return PHASE_STRATEGY_STRICT_TRIAD
        return name

    def _interaction_max(self) -> int:
        """
        Retrieves the maximum number of Action-Observe interactions allowed in Iterative mode.
        """
        proj = self._project_cfg()
        value = int(getattr(proj, "phase_interaction_max", 3) if proj else 3)
        return max(1, min(value, 16))

    def _act_require_tool_call(self) -> bool:
        """
        Checks if the Act phase is required to emit at least one tool call.
        """
        proj = self._project_cfg()
        return bool(getattr(proj, "phase_act_require_tool_call", True) if proj else True)

    def _act_require_productive_tool(self) -> bool:
        """
        Checks if the Act phase requires at least one productive tool call.
        """
        proj = self._project_cfg()
        return bool(getattr(proj, "phase_act_require_productive_tool", True) if proj else True)

    def _act_productive_from_interaction(self) -> int:
        """
        Retrieves the interaction index from which a productive tool call becomes mandatory.
        """
        proj = self._project_cfg()
        value = int(getattr(proj, "phase_act_productive_from_interaction", 2) if proj else 2)
        return max(1, min(value, 16))

    def _should_require_productive_for_interaction(self, interaction_idx: int) -> bool:
        """
        Determines if a productive tool is required for the given interaction index.
        """
        if not self._act_require_productive_tool():
            return False
        return int(interaction_idx) >= self._act_productive_from_interaction()

    def _act_violation_feedback(self, reason: str) -> str:
        """
        Provides feedback for violations specifically occurring during the Act phase.
        """
        if reason == "no_tool":
            return (
                "RULE VIOLATION: Act phase must emit at least one tool call. "
                "Reply again with concrete implementation tool calls."
            )
        if reason == "no_productive":
            return (
                "RULE VIOLATION: Act phase must include at least one productive tool "
                "(write_file/replace_content/insert_content/multi_replace/run_command). "
                "Reply again with productive tool calls."
            )
        return "RULE VIOLATION: Act phase output invalid. Retry with valid tool calls."

    def _run_iterative(self, state, simulation_directives: str, local_memory: str, inbox_msgs: str):
        """
        Executes the Iterative Action-Observe strategy.
        """
        proj = self._project_cfg()
        max_repeat = int(getattr(proj, "phase_repeat_limit", 2) if proj else 2)
        phase_retry_limit = max(1, int(getattr(proj, "phase_repeat_limit", 2) if proj else 2))
        interaction_max = self._interaction_max()
        pulse_meta = state.get("__pulse_meta", {}) if isinstance(state, dict) else {}
        pulse_id = str(pulse_meta.get("pulse_id", "manual"))
        pulse_reason = str(pulse_meta.get("reason", "unknown"))
        tracer = PulseTraceLogger(self.agent.project_id, self.agent.agent_id, pulse_id, pulse_reason)

        phases = base_phases()
        phase_order = phase_names(phases)
        allow_map = self._build_phase_allow_map(phases)
        policy = PhaseToolPolicy(
            phase_allow_map=allow_map,
            disabled_tools=self._disabled_tools(),
            max_repeat_same_call=max_repeat,
            explore_budget=9999,
        )

        terminal_reason = ""
        try:
            tracer.event("pulse_start", phase_name="reason", strategy=PHASE_STRATEGY_ITERATIVE_ACTION)

            # Stage 1: REASON
            # Rule: reason phase is text-only; any tool call is blocked and retried with feedback.
            reason_phase = phases[0]
            for reason_try in range(1, phase_retry_limit + 1):
                tracer.event("round_start", phase_name="reason", attempt=reason_try)
                reason_resp = self._think(
                    state, reason_phase, phase_order, simulation_directives, local_memory, inbox_msgs, pulse_meta
                )
                reason_calls = getattr(reason_resp, "tool_calls", []) or []
                tracer.event(
                    "llm_response",
                    phase_name="reason",
                    attempt=reason_try,
                    content_preview=PulseTraceLogger.clip(reason_resp.content or ""),
                    content_full=reason_resp.content or "",
                    tool_calls_full=reason_calls,
                    tool_calls=len(reason_calls),
                )
                if not reason_calls:
                    break
                for call in reason_calls:
                    tool_name = call.get("name", "")
                    obs = f"Policy Block: Tool '{tool_name}' is not allowed in phase 'reason'."
                    tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"
                    state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                    self._append_memory(
                        obs,
                        record_type=f"tool.{tool_name}.blocked",
                        payload={"tool_name": tool_name, "status": "blocked", "result": obs, "phase": "reason"},
                    )
                    tracer.event(
                        "tool_blocked",
                        phase_name="reason",
                        attempt=reason_try,
                        tool_name=tool_name,
                        block_reason=obs,
                    )
                if reason_try < phase_retry_limit:
                    fb = self._violation_feedback("reason")
                    state["messages"].append(SystemMessage(content=fb))
                    self._append_memory(
                        f"[PHASE_RETRY] reason -> {fb}",
                        record_type="phase.retry.reason",
                        payload={"phase": "reason", "message": fb},
                    )
                    tracer.event("phase_retry", phase_name="reason", attempt=reason_try, reason="tool_call_not_allowed")

            act_phase = phases[1]
            observe_phase = phases[2]
            for interaction_idx in range(1, interaction_max + 1):
                tracer.event("interaction_start", interaction=interaction_idx)

                # ACTION
                # Rule: action phase may emit multiple tool calls; tools are executed as a batch.
                tracer.event("round_start", phase_name="act", interaction=interaction_idx)
                act_resp = self._think(
                    state, act_phase, phase_order, simulation_directives, local_memory, inbox_msgs, pulse_meta
                )
                act_calls = getattr(act_resp, "tool_calls", []) or []
                tracer.event(
                    "llm_response",
                    phase_name="act",
                    interaction=interaction_idx,
                    content_preview=PulseTraceLogger.clip(act_resp.content or ""),
                    content_full=act_resp.content or "",
                    tool_calls_full=act_calls,
                    tool_calls=len(act_calls),
                )

                if self._act_require_tool_call() and len(act_calls) == 0:
                    fb = self._act_violation_feedback("no_tool")
                    state["messages"].append(SystemMessage(content=fb))
                    self._append_memory(
                        f"[PHASE_RETRY] act -> {fb}",
                        record_type="phase.retry.act",
                        payload={"phase": "act", "message": fb},
                    )
                    tracer.event(
                        "phase_retry",
                        phase_name="act",
                        interaction=interaction_idx,
                        attempt=1,
                        reason="no_tool_call",
                    )
                    tracer.event("continue_decision", reason="iterative_act_no_tool_call", interaction=interaction_idx)
                    terminal_reason = "iterative_act_no_tool_call"
                    return self._continue(state)

                if self._should_require_productive_for_interaction(interaction_idx):
                    names = [c.get("name", "") for c in act_calls]
                    if not any(n in PRODUCTIVE_ACT_TOOLS for n in names):
                        fb = self._act_violation_feedback("no_productive")
                        state["messages"].append(SystemMessage(content=fb))
                        self._append_memory(
                            f"[PHASE_RETRY] act -> {fb}",
                            record_type="phase.retry.act",
                            payload={"phase": "act", "message": fb},
                        )
                        tracer.event(
                            "phase_retry",
                            phase_name="act",
                            interaction=interaction_idx,
                            attempt=1,
                            reason="no_productive_tool_call",
                        )
                        tracer.event(
                            "continue_decision",
                            reason="iterative_act_no_productive_tool",
                            interaction=interaction_idx,
                        )
                        terminal_reason = "iterative_act_no_productive_tool"
                        return self._continue(state)

                for call in act_calls:
                    tool_name = call.get("name", "")
                    args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                    tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"
                    block_reason = policy.check("act", tool_name, args)
                    if block_reason:
                        obs = f"Policy Block: {block_reason}"
                        state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                        self._append_memory(
                            obs,
                            record_type=f"tool.{tool_name}.blocked",
                            payload={"tool_name": tool_name, "status": "blocked", "result": obs, "phase": "act"},
                        )
                        tracer.event(
                            "tool_blocked",
                            phase_name="act",
                            interaction=interaction_idx,
                            tool_name=tool_name,
                            args_preview=PulseTraceLogger.clip(args),
                            args_full=args,
                            block_reason=block_reason,
                        )
                        injected = inject_inbox_after_action_if_any(state, self.agent.project_id, self.agent.agent_id)
                        if injected > 0:
                            self._append_memory(
                                f"[EVENT_INJECTED] {injected} inbox event(s) appended after action.",
                                record_type="agent.event.injected",
                                payload={"count": int(injected)},
                            )
                        continue
                    obs = self.agent.execute_tool(tool_name, args)
                    policy.record(tool_name, args)
                    state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                    tracer.event(
                        "tool_executed",
                        phase_name="act",
                        interaction=interaction_idx,
                        tool_name=tool_name,
                        args_preview=PulseTraceLogger.clip(args),
                        args_full=args,
                        obs_preview=PulseTraceLogger.clip(obs),
                        obs_full=obs,
                    )
                    injected = inject_inbox_after_action_if_any(state, self.agent.project_id, self.agent.agent_id)
                    if injected > 0:
                        self._append_memory(
                            f"[EVENT_INJECTED] {injected} inbox event(s) appended after action.",
                            record_type="agent.event.injected",
                            payload={"count": int(injected)},
                        )

                # OBSERVE
                # Rule: observe phase can only finalize; all other tools are blocked.
                observed_finalize = False
                for observe_try in range(1, phase_retry_limit + 1):
                    tracer.event("round_start", phase_name="observe", interaction=interaction_idx, attempt=observe_try)
                    observe_resp = self._think(
                        state, observe_phase, phase_order, simulation_directives, local_memory, inbox_msgs, pulse_meta
                    )
                    observe_calls = getattr(observe_resp, "tool_calls", []) or []
                    tracer.event(
                        "llm_response",
                        phase_name="observe",
                        interaction=interaction_idx,
                        attempt=observe_try,
                        content_preview=PulseTraceLogger.clip(observe_resp.content or ""),
                        content_full=observe_resp.content or "",
                        tool_calls_full=observe_calls,
                        tool_calls=len(observe_calls),
                    )

                    invalid_calls = [c for c in observe_calls if c.get("name", "") != "finalize"]
                    if invalid_calls:
                        for call in invalid_calls:
                            tool_name = call.get("name", "")
                            args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                            tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"
                            obs = "Policy Block: Tool '{}' is not allowed in phase 'observe'.".format(tool_name)
                            state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                            self._append_memory(
                                obs,
                                record_type=f"tool.{tool_name}.blocked",
                                payload={"tool_name": tool_name, "status": "blocked", "result": obs, "phase": "observe"},
                            )
                            tracer.event(
                                "tool_blocked",
                                phase_name="observe",
                                interaction=interaction_idx,
                                attempt=observe_try,
                                tool_name=tool_name,
                                args_preview=PulseTraceLogger.clip(args),
                                args_full=args,
                                block_reason=obs,
                            )
                        if observe_try < phase_retry_limit:
                            fb = self._violation_feedback("observe")
                            state["messages"].append(SystemMessage(content=fb))
                            self._append_memory(
                                f"[PHASE_RETRY] observe -> {fb}",
                                record_type="phase.retry.observe",
                                payload={"phase": "observe", "message": fb},
                            )
                            tracer.event(
                                "phase_retry",
                                phase_name="observe",
                                interaction=interaction_idx,
                                attempt=observe_try,
                                reason="non_finalize_tool_call",
                            )
                            continue
                        break

                    finalize_calls = [c for c in observe_calls if c.get("name", "") == "finalize"]
                    if finalize_calls:
                        call = finalize_calls[0]
                        args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                        tool_call_id = call.get("id") or f"finalize_{uuid.uuid4().hex[:8]}"
                        obs = self.agent.execute_tool("finalize", args)
                        try:
                            _sleep_sec = int(args.get("sleep_sec", 0) or 0)
                        except Exception:
                            _sleep_sec = 0
                        state["__finalize_control"] = {
                            "mode": str(args.get("mode", "done") or "done").strip().lower(),
                            "sleep_sec": _sleep_sec,
                            "reason": str(args.get("reason", "") or ""),
                        }
                        state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name="finalize"))
                        tracer.event(
                            "tool_executed",
                            phase_name="observe",
                            interaction=interaction_idx,
                            attempt=observe_try,
                            tool_name="finalize",
                            args_preview=PulseTraceLogger.clip(args),
                            args_full=args,
                            obs_preview=PulseTraceLogger.clip(obs),
                            obs_full=obs,
                        )
                        tracer.event("finish_decision", reason="observe_finalize_called", interaction=interaction_idx)
                        terminal_reason = "observe_finalize_called"
                        observed_finalize = True
                        break
                    break

                if observed_finalize:
                    return self._finish(state)
                tracer.event("interaction_end", interaction=interaction_idx, result="continue_to_next_action")
                local_memory = self.agent._load_local_memory()

            tracer.event("continue_decision", reason="iterative_interaction_cap_reached_no_finalize")
            terminal_reason = "iterative_interaction_cap_reached_no_finalize"
            return self._continue(state)
        finally:
            tracer.event(
                "pulse_end",
                next_step=state.get("next_step", ""),
                terminal_reason=terminal_reason or "unknown",
                phase_idx=0,
                phase_name="reason",
                no_progress_rounds=0,
            )
            tracer.flush()

    def run(self, state, simulation_directives: str, local_memory: str, inbox_msgs: str):
        """
        Dispatches the agent pulse execution to the configured strategy.
        """
        strategy = self._strategy_name()
        if strategy == PHASE_STRATEGY_ITERATIVE_ACTION:
            return self._run_iterative(state, simulation_directives, local_memory, inbox_msgs)
        proj = self._project_cfg()
        max_repeat = int(getattr(proj, "phase_repeat_limit", 2) if proj else 2)
        phase_retry_limit = max(1, int(getattr(proj, "phase_repeat_limit", 2) if proj else 2))
        pulse_meta = state.get("__pulse_meta", {}) if isinstance(state, dict) else {}
        pulse_id = str(pulse_meta.get("pulse_id", "manual"))
        pulse_reason = str(pulse_meta.get("reason", "unknown"))
        tracer = PulseTraceLogger(self.agent.project_id, self.agent.agent_id, pulse_id, pulse_reason)

        phases = base_phases()
        phase_order = phase_names(phases)
        allow_map = self._build_phase_allow_map(phases)
        policy = PhaseToolPolicy(
            phase_allow_map=allow_map,
            disabled_tools=self._disabled_tools(),
            max_repeat_same_call=max_repeat,
            explore_budget=9999,
        )

        terminal_reason = ""
        try:
            tracer.event("pulse_start", phase_name="reason")

            # Stage 1: REASON (text only; no tool execution)
            reason_phase = phases[0]
            for reason_try in range(1, phase_retry_limit + 1):
                tracer.event("round_start", phase_name="reason", attempt=reason_try)
                reason_resp = self._think(
                    state, reason_phase, phase_order, simulation_directives, local_memory, inbox_msgs, pulse_meta
                )
                reason_calls = getattr(reason_resp, "tool_calls", []) or []
                tracer.event(
                    "llm_response",
                    phase_name="reason",
                    attempt=reason_try,
                    content_preview=PulseTraceLogger.clip(reason_resp.content or ""),
                    content_full=reason_resp.content or "",
                    tool_calls_full=reason_calls,
                    tool_calls=len(reason_calls),
                )
                if not reason_calls:
                    break

                for call in reason_calls:
                    tool_name = call.get("name", "")
                    obs = f"Policy Block: Tool '{tool_name}' is not allowed in phase 'reason'."
                    tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"
                    state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                    self._append_memory(
                        obs,
                        record_type=f"tool.{tool_name}.blocked",
                        payload={"tool_name": tool_name, "status": "blocked", "result": obs, "phase": "reason"},
                    )
                    tracer.event(
                        "tool_blocked",
                        phase_name="reason",
                        attempt=reason_try,
                        tool_name=tool_name,
                        block_reason=obs,
                    )

                if reason_try < phase_retry_limit:
                    fb = self._violation_feedback("reason")
                    state["messages"].append(SystemMessage(content=fb))
                    self._append_memory(
                        f"[PHASE_RETRY] reason -> {fb}",
                        record_type="phase.retry.reason",
                        payload={"phase": "reason", "message": fb},
                    )
                    tracer.event("phase_retry", phase_name="reason", attempt=reason_try, reason="tool_call_not_allowed")

            # Stage 2: ACTION (batch tools)
            # Rule: strict triad runs exactly one action batch in this pulse.
            act_phase = phases[1]
            tracer.event("round_start", phase_name="act")
            act_resp = self._think(
                state, act_phase, phase_order, simulation_directives, local_memory, inbox_msgs, pulse_meta
            )
            act_calls = getattr(act_resp, "tool_calls", []) or []
            tracer.event(
                "llm_response",
                phase_name="act",
                content_preview=PulseTraceLogger.clip(act_resp.content or ""),
                content_full=act_resp.content or "",
                tool_calls_full=act_calls,
                tool_calls=len(act_calls),
            )

            if self._act_require_tool_call() and len(act_calls) == 0:
                fb = self._act_violation_feedback("no_tool")
                state["messages"].append(SystemMessage(content=fb))
                self._append_memory(
                    f"[PHASE_RETRY] act -> {fb}",
                    record_type="phase.retry.act",
                    payload={"phase": "act", "message": fb},
                )
                tracer.event("phase_retry", phase_name="act", attempt=1, reason="no_tool_call")
                tracer.event("continue_decision", reason="act_no_tool_call")
                terminal_reason = "act_no_tool_call"
                return self._continue(state)

            if self._should_require_productive_for_interaction(1):
                names = [c.get("name", "") for c in act_calls]
                if not any(n in PRODUCTIVE_ACT_TOOLS for n in names):
                    fb = self._act_violation_feedback("no_productive")
                    state["messages"].append(SystemMessage(content=fb))
                    self._append_memory(
                        f"[PHASE_RETRY] act -> {fb}",
                        record_type="phase.retry.act",
                        payload={"phase": "act", "message": fb},
                    )
                    tracer.event("phase_retry", phase_name="act", attempt=1, reason="no_productive_tool_call")
                    tracer.event("continue_decision", reason="act_no_productive_tool")
                    terminal_reason = "act_no_productive_tool"
                    return self._continue(state)

            for call in act_calls:
                tool_name = call.get("name", "")
                args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"
                block_reason = policy.check("act", tool_name, args)
                if block_reason:
                    obs = f"Policy Block: {block_reason}"
                    state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                    self._append_memory(
                        obs,
                        record_type=f"tool.{tool_name}.blocked",
                        payload={"tool_name": tool_name, "status": "blocked", "result": obs, "phase": "act"},
                    )
                    tracer.event(
                        "tool_blocked",
                        phase_name="act",
                        tool_name=tool_name,
                        args_preview=PulseTraceLogger.clip(args),
                        args_full=args,
                        block_reason=block_reason,
                    )
                    injected = inject_inbox_after_action_if_any(state, self.agent.project_id, self.agent.agent_id)
                    if injected > 0:
                        self._append_memory(
                            f"[EVENT_INJECTED] {injected} inbox event(s) appended after action.",
                            record_type="agent.event.injected",
                            payload={"count": int(injected)},
                        )
                    continue

                obs = self.agent.execute_tool(tool_name, args)
                policy.record(tool_name, args)
                state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                tracer.event(
                    "tool_executed",
                    phase_name="act",
                    tool_name=tool_name,
                    args_preview=PulseTraceLogger.clip(args),
                    args_full=args,
                    obs_preview=PulseTraceLogger.clip(obs),
                    obs_full=obs,
                )
                injected = inject_inbox_after_action_if_any(state, self.agent.project_id, self.agent.agent_id)
                if injected > 0:
                    self._append_memory(
                        f"[EVENT_INJECTED] {injected} inbox event(s) appended after action.",
                        record_type="agent.event.injected",
                        payload={"count": int(injected)},
                    )

            # Stage 3: OBSERVE (only finalize is allowed)
            observe_phase = phases[2]
            for observe_try in range(1, phase_retry_limit + 1):
                tracer.event("round_start", phase_name="observe", attempt=observe_try)
                observe_resp = self._think(
                    state, observe_phase, phase_order, simulation_directives, local_memory, inbox_msgs, pulse_meta
                )
                observe_calls = getattr(observe_resp, "tool_calls", []) or []
                tracer.event(
                    "llm_response",
                    phase_name="observe",
                    attempt=observe_try,
                    content_preview=PulseTraceLogger.clip(observe_resp.content or ""),
                    content_full=observe_resp.content or "",
                    tool_calls_full=observe_calls,
                    tool_calls=len(observe_calls),
                )

                invalid_calls = [c for c in observe_calls if c.get("name", "") != "finalize"]
                if invalid_calls:
                    for call in invalid_calls:
                        tool_name = call.get("name", "")
                        args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                        tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"
                        obs = "Policy Block: Tool '{}' is not allowed in phase 'observe'.".format(tool_name)
                        state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                        self._append_memory(
                            obs,
                            record_type=f"tool.{tool_name}.blocked",
                            payload={"tool_name": tool_name, "status": "blocked", "result": obs, "phase": "observe"},
                        )
                        tracer.event(
                            "tool_blocked",
                            phase_name="observe",
                            attempt=observe_try,
                            tool_name=tool_name,
                            args_preview=PulseTraceLogger.clip(args),
                            args_full=args,
                            block_reason=obs,
                        )
                    if observe_try < phase_retry_limit:
                        fb = self._violation_feedback("observe")
                        state["messages"].append(SystemMessage(content=fb))
                        self._append_memory(
                            f"[PHASE_RETRY] observe -> {fb}",
                            record_type="phase.retry.observe",
                            payload={"phase": "observe", "message": fb},
                        )
                        tracer.event(
                            "phase_retry",
                            phase_name="observe",
                            attempt=observe_try,
                            reason="non_finalize_tool_call",
                        )
                        continue
                    break

                finalize_calls = [c for c in observe_calls if c.get("name", "") == "finalize"]
                if finalize_calls:
                    call = finalize_calls[0]
                    args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                    tool_call_id = call.get("id") or f"finalize_{uuid.uuid4().hex[:8]}"
                    obs = self.agent.execute_tool("finalize", args)
                    try:
                        _sleep_sec = int(args.get("sleep_sec", 0) or 0)
                    except Exception:
                        _sleep_sec = 0
                    state["__finalize_control"] = {
                        "mode": str(args.get("mode", "done") or "done").strip().lower(),
                        "sleep_sec": _sleep_sec,
                        "reason": str(args.get("reason", "") or ""),
                    }
                    state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name="finalize"))
                    tracer.event(
                        "tool_executed",
                        phase_name="observe",
                        attempt=observe_try,
                        tool_name="finalize",
                        args_preview=PulseTraceLogger.clip(args),
                        args_full=args,
                        obs_preview=PulseTraceLogger.clip(obs),
                        obs_full=obs,
                    )
                    tracer.event("finish_decision", reason="observe_finalize_called")
                    terminal_reason = "observe_finalize_called"
                    return self._finish(state)
                break

            tracer.event("continue_decision", reason="observe_no_finalize_return_to_reason")
            terminal_reason = "observe_no_finalize_return_to_reason"
            return self._continue(state)
        finally:
            tracer.event(
                "pulse_end",
                next_step=state.get("next_step", ""),
                terminal_reason=terminal_reason or "unknown",
                phase_idx=0,
                phase_name="reason",
                no_progress_rounds=0,
            )
            tracer.flush()
