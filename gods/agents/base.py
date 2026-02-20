"""Gods Platform - Agent Node Definitions."""
from __future__ import annotations

import logging
import time

from gods.agents.brain import GodBrain
from gods.agents.orchestrators import ChronosOrchestrator, NikeOrchestrator, ThemisOrchestrator
from gods.agents.tool_policy import is_social_disabled, is_tool_disabled
from gods.config import runtime_config
from gods.mnemosyne import MemoryIntent, record_intent

from gods.mnemosyne.facade import ensure_agent_memory_seeded, load_agent_directives, load_chronicle_for_context
from gods.paths import agent_dir
from gods.state import GodsState

logger = logging.getLogger(__name__)


class GodAgent:
    """
    Dynamic Agent that derives identity and behavior from filesystem metadata.
    Source of truth: projects/{project_id}/mnemosyne/agent_profiles/{agent_id}.md
    """

    def __init__(self, agent_id: str, project_id: str = "default"):
        self.agent_id = agent_id
        self.project_id = project_id
        self.agent_dir = agent_dir(project_id, agent_id)

        self.directives = load_agent_directives(project_id, agent_id)
        ensure_agent_memory_seeded(project_id, agent_id, self.directives, self.agent_dir)

        self.brain = GodBrain(agent_id=agent_id, project_id=project_id)
        self.themis = ThemisOrchestrator(
            project_id=project_id,
            agent_id=agent_id,
            agent_dir=self.agent_dir,
            intent_recorder=self._record_intent,
        )

    def _build_inbox_context_hint(self) -> str:
        if is_tool_disabled(self.project_id, self.agent_id, "check_inbox"):
            return (
                "Inbox events are pre-injected by scheduler. "
                "check_inbox is disabled by policy (debug fallback only)."
            )
        return "Inbox events are pre-injected by scheduler. Use check_inbox only for audit fallback."

    def _build_behavior_directives(self) -> str:
        if is_social_disabled(self.project_id, self.agent_id):
            return (
                "# LOCAL EXECUTION PROTOCOL\n"
                "- Social tools are disabled for this agent.\n"
                "- Do NOT attempt inbox/social actions.\n"
                "- Focus only on local implementation, verification, and completion."
            )
        return ""

    def process(self, state: GodsState) -> GodsState:
        ChronosOrchestrator.merge(self.project_id, self.agent_id, state)
        out = NikeOrchestrator.run(self, state)
        return ChronosOrchestrator.finalize(self.project_id, self.agent_id, out)

    def _load_local_memory(self) -> str:
        memory = str(load_chronicle_for_context(self.project_id, self.agent_id, fallback="") or "")
        return memory if memory else "No personal chronicles yet."

    def _record_intent(self, intent: MemoryIntent):
        return record_intent(intent)

    @staticmethod
    def _is_transient_llm_error_text(text: str) -> bool:
        raw = str(text or "").strip().lower()
        return raw.startswith("error in reasoning:") or raw.startswith("❌ error:")

    @staticmethod
    def _finalize_control_from_args(args: dict) -> dict:
        return ThemisOrchestrator.finalize_control_from_args(args)

    def execute_tool(self, name: str, args: dict, node_name: str = "") -> str:
        return self.themis.execute_tool(name, args, node_name=node_name)



    def get_tools(self):
        return self.themis.get_tools()

    def get_tools_for_node(self, node_name: str):
        return self.themis.get_tools_for_node(node_name)

    def _render_tools_desc(self, node_name: str = "llm_think") -> str:
        return self.themis.render_tools_desc(node_name)


# Factory function for LangGraph nodes

def create_god_node(agent_id: str):
    """
    Creates a LangGraph node function for a specific agent.
    """

    def node_func(state: GodsState) -> GodsState:
        project_id = state.get("project_id", runtime_config.current_project)

        # Check if this agent chose to abstain from this thread
        abstained_list = state.get("abstained", [])
        if agent_id in abstained_list:
            print(f"[{agent_id}] Abstained from this Synod. Skipping...")
            state["next_step"] = "finish"  # Handover to next
            return state

        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        return agent.process(state)

    return node_func


# Node helpers

def genesis_node(state: GodsState) -> GodsState:
    """
    Node function specialized for the 'genesis' agent.
    """

    return create_god_node("genesis")(state)


def coder_node(state: GodsState) -> GodsState:
    """
    Node function specialized for the 'coder' agent.
    """

    return create_god_node("coder")(state)
