"""
Phase-based autonomous runtime for GodAgent.
Provides modular stage control, tool policy gating, and deterministic transitions.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from gods.config import runtime_config
from gods.prompts import prompt_registry


EXPLORATORY_TOOLS = {"list_dir", "read_file", "check_inbox", "list_agents"}
SOCIAL_TOOLS = {
    "check_inbox",
    "send_message",
    "send_to_human",
    "post_to_synod",
    "abstain_from_synod",
    "record_protocol",
    "list_agents",
}


@dataclass(frozen=True)
class AgentPhase:
    name: str
    prompt_template: str
    allowed_tools: Tuple[str, ...]


def _base_phases() -> List[AgentPhase]:
    return [
        AgentPhase(
            name="discover",
            prompt_template="agent_phase_discover",
            allowed_tools=("list_dir", "read_file", "run_command", "write_file"),
        ),
        AgentPhase(
            name="implement",
            prompt_template="agent_phase_implement",
            allowed_tools=(
                "read_file",
                "write_file",
                "replace_content",
                "insert_content",
                "multi_replace",
                "run_command",
                "list_dir",
            ),
        ),
        AgentPhase(
            name="verify",
            prompt_template="agent_phase_verify",
            allowed_tools=("run_command", "read_file", "list_dir", "write_file"),
        ),
        AgentPhase(
            name="finalize",
            prompt_template="agent_phase_finalize",
            allowed_tools=("write_file", "read_file", "list_dir", "run_command"),
        ),
    ]


def phase_names(phases: List[AgentPhase]) -> List[str]:
    return [p.name for p in phases]


class PhaseToolPolicy:
    """
    Per-pulse policy gate:
    - phase allow-list
    - repeated same-call blocking
    - exploratory budget limiting
    """

    def __init__(
        self,
        phase_allow_map: Dict[str, set],
        disabled_tools: set,
        max_repeat_same_call: int = 2,
        explore_budget: int = 3,
    ):
        self.phase_allow_map = phase_allow_map
        self.disabled_tools = disabled_tools
        self.max_repeat_same_call = max(1, max_repeat_same_call)
        self.explore_budget = max(1, explore_budget)
        self._last_sig: Optional[str] = None
        self._same_sig_count: int = 0
        self._explore_count: int = 0

    def _signature(self, tool_name: str, args: dict) -> str:
        try:
            normalized = json.dumps(args, sort_keys=True, ensure_ascii=False)
        except Exception:
            normalized = str(args)
        return f"{tool_name}:{normalized}"

    def check(self, phase_name: str, tool_name: str, args: dict) -> Optional[str]:
        if tool_name in self.disabled_tools:
            return f"Tool '{tool_name}' is disabled."

        allowed = self.phase_allow_map.get(phase_name, set())
        if tool_name not in allowed:
            return f"Tool '{tool_name}' is not allowed in phase '{phase_name}'."

        sig = self._signature(tool_name, args)
        if self._last_sig == sig and self._same_sig_count >= self.max_repeat_same_call:
            return f"Repeated call blocked: {tool_name} with same arguments."

        if tool_name in EXPLORATORY_TOOLS and self._explore_count >= self.explore_budget:
            return f"Exploration budget exceeded for this pulse ({self.explore_budget})."

        return None

    def record(self, tool_name: str, args: dict):
        sig = self._signature(tool_name, args)
        if self._last_sig == sig:
            self._same_sig_count += 1
        else:
            self._last_sig = sig
            self._same_sig_count = 1
        if tool_name in EXPLORATORY_TOOLS:
            self._explore_count += 1


class AgentPhaseRuntime:
    """
    Deterministic phase runner around model<->tool loop.
    """

    def __init__(self, agent):
        self.agent = agent

    def _project_cfg(self):
        return runtime_config.projects.get(self.agent.project_id)

    def _disabled_tools(self) -> set:
        proj = self._project_cfg()
        if not proj:
            return set()
        settings = proj.agent_settings.get(self.agent.agent_id)
        if not settings:
            return set()
        return set(settings.disabled_tools or [])

    def _build_phase_allow_map(self, phases: List[AgentPhase]) -> Dict[str, set]:
        disabled = self._disabled_tools()
        allow_map: Dict[str, set] = {}
        for phase in phases:
            allow = set(phase.allowed_tools)
            if (SOCIAL_TOOLS & disabled) == SOCIAL_TOOLS:
                allow -= SOCIAL_TOOLS
            allow_map[phase.name] = allow
        return allow_map

    def _phase_prompt(self, phase: AgentPhase, phase_order: List[str]) -> str:
        return prompt_registry.render(
            phase.prompt_template,
            project_id=self.agent.project_id,
            phase_name=phase.name,
            phase_order=" -> ".join(phase_order),
            allowed_tools=", ".join(phase.allowed_tools),
        )

    def _is_success_obs(self, tool_name: str, observation: str) -> bool:
        if tool_name != "run_command":
            return False
        return "exit=0" in (observation or "")

    def _advance_phase(self, phase_idx: int, phases: List[AgentPhase]) -> int:
        return min(phase_idx + 1, len(phases) - 1)

    def _next_phase_index(self, phase_idx: int, phases: List[AgentPhase], tool_name: str, observation: str) -> int:
        current = phases[phase_idx].name
        if current == "discover" and tool_name in {"write_file", "replace_content", "insert_content", "multi_replace"}:
            return self._advance_phase(phase_idx, phases)
        if current == "implement" and self._is_success_obs(tool_name, observation):
            return self._advance_phase(phase_idx, phases)
        if current == "verify" and self._is_success_obs(tool_name, observation):
            return self._advance_phase(phase_idx, phases)
        return phase_idx

    def run(self, state, simulation_directives: str, local_memory: str, inbox_msgs: str):
        proj = self._project_cfg()
        max_rounds = int(getattr(proj, "tool_loop_max", 8) if proj else 8)
        max_rounds = max(1, min(max_rounds, 64))
        max_repeat = int(getattr(proj, "phase_repeat_limit", 2) if proj else 2)
        explore_budget = int(getattr(proj, "phase_explore_budget", 3) if proj else 3)
        no_progress_limit = int(getattr(proj, "phase_no_progress_limit", 3) if proj else 3)
        single_tool = bool(getattr(proj, "phase_single_tool_call", True) if proj else True)

        phases = _base_phases()
        phase_order = phase_names(phases)
        phase_idx = 0
        no_progress_rounds = 0
        policy = PhaseToolPolicy(
            phase_allow_map=self._build_phase_allow_map(phases),
            disabled_tools=self._disabled_tools(),
            max_repeat_same_call=max_repeat,
            explore_budget=explore_budget,
        )

        for _ in range(max_rounds):
            phase = phases[phase_idx]
            phase_block = self._phase_prompt(phase, phase_order)
            context = self.agent.build_context(
                state=state,
                directives=simulation_directives,
                local_memory=local_memory,
                inbox_content=inbox_msgs,
                phase_block=phase_block,
                phase_name=phase.name,
            )

            llm_messages = [SystemMessage(content=context)] + state.get("messages", [])[-8:]
            response: AIMessage = self.agent.brain.think_with_tools(llm_messages, self.agent.get_tools())
            state["messages"].append(response)
            self.agent._append_to_memory(response.content or "[No textual response]")

            tool_calls = getattr(response, "tool_calls", []) or []
            if not tool_calls:
                if phase.name in {"verify", "finalize"}:
                    state["next_step"] = "finish"
                    return state
                phase_idx = self._advance_phase(phase_idx, phases)
                no_progress_rounds += 1
                if no_progress_rounds >= no_progress_limit:
                    state["next_step"] = "continue"
                    return state
                continue

            if single_tool:
                tool_calls = tool_calls[:1]

            round_progress = False
            for call in tool_calls:
                tool_name = call.get("name", "")
                args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"

                block_reason = policy.check(phase.name, tool_name, args)
                if block_reason:
                    obs = f"Policy Block: {block_reason}"
                    state["messages"].append(ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name))
                    self.agent._append_to_memory(f"[[ACTION]] {tool_name} -> {obs}")
                    continue

                obs = self.agent.execute_tool(tool_name, args)
                policy.record(tool_name, args)
                obs_for_context = self.agent._clip_text(
                    obs,
                    int(getattr(proj, "history_clip_chars", 600) if proj else 600),
                )
                state["messages"].append(ToolMessage(content=obs_for_context, tool_call_id=tool_call_id, name=tool_name))
                self.agent._append_to_memory(f"[[ACTION]] {tool_name} -> {obs}")

                if tool_name == "post_to_synod":
                    state["next_step"] = "escalated"
                    return state
                if tool_name == "abstain_from_synod":
                    if "abstained" not in state or state["abstained"] is None:
                        state["abstained"] = []
                    if self.agent.agent_id not in state["abstained"]:
                        state["abstained"].append(self.agent.agent_id)
                    state["next_step"] = "abstained"
                    return state

                phase_idx = self._next_phase_index(phase_idx, phases, tool_name, obs)
                round_progress = round_progress or tool_name not in EXPLORATORY_TOOLS

            local_memory = self.agent._load_local_memory()
            if round_progress:
                no_progress_rounds = 0
            else:
                no_progress_rounds += 1
                if no_progress_rounds >= no_progress_limit:
                    state["next_step"] = "continue"
                    return state

        self.agent._append_to_memory("Reached phase loop safety cap in this pulse. Will continue next pulse.")
        state["next_step"] = "continue"
        return state
