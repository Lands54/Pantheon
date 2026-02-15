"""Phase runtime policy and phase definitions."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

PRODUCTIVE_ACT_TOOLS = {"write_file", "replace_content", "insert_content", "multi_replace", "run_command"}


@dataclass(frozen=True)
class AgentPhase:
    name: str
    prompt_template: str
    allowed_tools: Tuple[str, ...]


def base_phases() -> List[AgentPhase]:
    return [
        AgentPhase(
            name="reason",
            prompt_template="agent_phase_reason",
            allowed_tools=(),
        ),
        AgentPhase(
            name="act",
            prompt_template="agent_phase_act",
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
            name="observe",
            prompt_template="agent_phase_observe",
            allowed_tools=("finalize",),
        ),
    ]


def phase_names(phases: List[AgentPhase]) -> List[str]:
    return [p.name for p in phases]


class PhaseToolPolicy:
    """
    Per-pulse policy gate:
    - phase allow-list
    - repeated same-call blocking (in action phase)
    """

    def __init__(
        self,
        phase_allow_map: Dict[str, set],
        disabled_tools: set,
        max_repeat_same_call: int = 2,
        explore_budget: int = 9999,  # kept for backward-compatible ctor shape
    ):
        self.phase_allow_map = phase_allow_map
        self.disabled_tools = disabled_tools
        self.max_repeat_same_call = max(1, max_repeat_same_call)
        self._same_sig_count: dict[str, int] = {}

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
        if self._same_sig_count.get(sig, 0) >= self.max_repeat_same_call:
            return f"Repeated call blocked: {tool_name} with same arguments."

        return None

    def record(self, tool_name: str, args: dict):
        sig = self._signature(tool_name, args)
        self._same_sig_count[sig] = self._same_sig_count.get(sig, 0) + 1
