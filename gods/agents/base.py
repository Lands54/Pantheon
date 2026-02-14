"""
Gods Platform - Agent Node Definitions
Agents load their core logic directly from their respective agents/{id}/agent.md files.
"""
import uuid
import re
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from gods.state import GodsState
from gods.agents.brain import GodBrain
from gods.prompts import prompt_registry
from gods.tools import GODS_TOOLS
from gods.tools.communication import reset_inbox_guard
from gods.config import runtime_config
from gods.agents.phase_runtime import AgentPhaseRuntime
from gods.agents.tool_policy import is_social_disabled, is_tool_disabled
from pathlib import Path


class GodAgent:
    """
    Dynamic Agent that derives identity and behavior from filesystem metadata.
    Source of truth: projects/{project_id}/agents/{agent_id}/agent.md
    """
    def __init__(self, agent_id: str, project_id: str = "default"):
        self.agent_id = agent_id
        self.project_id = project_id
        self.agent_dir = Path(f"projects/{project_id}/agents/{agent_id}")
        self.agent_md = self.agent_dir / "agent.md"
        
        # Load behavior description from agent.md
        self.directives = self._load_directives()
        self._ensure_memory_seeded()
        
        # Initialize brain with specific settings from config
        self.brain = GodBrain(agent_id=agent_id, project_id=project_id)

    def _load_directives(self) -> str:
        """Load the core mission/logic from agent.md"""
        if self.agent_md.exists():
            return self.agent_md.read_text(encoding="utf-8")
        return f"Agent ID: {self.agent_id}\n(No agent.md found. Please create one in {self.agent_md})"

    def _ensure_memory_seeded(self):
        """
        Seed memory.md with directives snapshot once, so agent doesn't need to read agent.md.
        """
        mem_path = self.agent_dir / "memory.md"
        if mem_path.exists():
            try:
                if mem_path.stat().st_size > 0:
                    return
            except Exception:
                return
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        seed = (
            "### SYSTEM_SEED\n"
            "Directives snapshot (from agent.md):\n\n"
            f"{self.directives}\n\n---\n"
        )
        mem_path.write_text(seed, encoding="utf-8")
    
    def _build_inbox_context_hint(self) -> str:
        if is_tool_disabled(self.project_id, self.agent_id, "check_inbox"):
            return "Inbox access is disabled by policy. Do NOT call check_inbox. Continue local work."
        return "Inbox is not pre-fetched. Use check_inbox tool when needed."

    def _build_behavior_directives(self) -> str:
        if is_social_disabled(self.project_id, self.agent_id):
            return (
                f"{self.directives}\n\n"
                "# LOCAL EXECUTION PROTOCOL\n"
                "- Social tools are disabled for this agent.\n"
                "- Do NOT attempt inbox/social actions.\n"
                "- Focus only on local implementation, verification, and completion."
            )
        return prompt_registry.render(
            "agent_social_protocol",
            project_id=self.project_id,
            directives=self.directives,
            agent_id=self.agent_id,
        )

    def process(self, state: GodsState) -> GodsState:
        """Autonomous Agent Pulse with phase runtime (fallback to legacy loop when disabled)."""
        proj = runtime_config.projects.get(self.project_id)
        phase_mode_enabled = bool(getattr(proj, "phase_mode_enabled", True) if proj else True)
        if phase_mode_enabled:
            inbox_msgs = self._build_inbox_context_hint()
            local_memory = self._load_local_memory()
            simulation_directives = self._build_behavior_directives()
            print(f"[{self.agent_id}] Pulsing (Phase Runtime)...")
            return AgentPhaseRuntime(self).run(
                state=state,
                simulation_directives=simulation_directives,
                local_memory=local_memory,
                inbox_msgs=inbox_msgs,
            )

        # --- Legacy loop ---
        max_tool_rounds = int(getattr(proj, "tool_loop_max", 8) if proj else 8)
        max_tool_rounds = max(1, min(max_tool_rounds, 64))
        inbox_msgs = self._build_inbox_context_hint()
        local_memory = self._load_local_memory()
        simulation_directives = self._build_behavior_directives()

        print(f"[{self.agent_id}] Pulsing (Self-Aware Thinking)...")

        for _ in range(max_tool_rounds):
            context = self.build_context(state, simulation_directives, local_memory, inbox_msgs)
            llm_messages = [SystemMessage(content=context)] + state.get("messages", [])[-8:]
            response = self.brain.think_with_tools(
                llm_messages,
                self.get_tools(),
                trace_meta=state.get("__pulse_meta", {}) if isinstance(state, dict) else {},
            )

            state["messages"].append(response)
            self._append_to_memory(response.content or "[No textual response]")

            tool_calls = getattr(response, "tool_calls", []) or []
            if not tool_calls:
                state["next_step"] = "finish"
                return state

            for call in tool_calls:
                tool_name = call.get("name", "")
                args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"

                obs = self.execute_tool(tool_name, args)
                state["messages"].append(
                    ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name)
                )
                self._append_to_memory(f"[[ACTION]] {tool_name} -> {obs}")

                if tool_name == "post_to_synod":
                    state["next_step"] = "escalated"
                    return state
                if tool_name == "abstain_from_synod":
                    if "abstained" not in state or state["abstained"] is None:
                        state["abstained"] = []
                    if self.agent_id not in state["abstained"]:
                        state["abstained"].append(self.agent_id)
                    state["next_step"] = "abstained"
                    return state

            # refresh local memory snapshot for next loop iteration
            local_memory = self._load_local_memory()

        # Safety guard: if model keeps issuing tools forever, yield and let scheduler pulse later.
        self._append_to_memory("Reached tool loop safety cap in this pulse. Will continue next pulse.")
        state["next_step"] = "continue"
        return state

    def _load_local_memory(self) -> str:
        """Load full memory.md after automatic compaction."""
        mem_path = self.agent_dir / "memory.md"
        self._maybe_compact_memory(mem_path)
        if mem_path.exists():
            return mem_path.read_text(encoding="utf-8")
        return "No personal chronicles yet."

    def _append_to_memory(self, text: str):
        """Append a thought or event to the human-readable memory.md"""
        from datetime import datetime
        mem_path = self.agent_dir / "memory.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n### 📖 Entry [{timestamp}]\n{text or ''}\n\n---\n"
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(entry)
        self._maybe_compact_memory(mem_path)

    def _maybe_compact_memory(self, mem_path: Path):
        """
        Keep memory bounded by rolling old content into a compact archive note.
        This is deterministic and cheap (no extra model calls).
        """
        if not mem_path.exists():
            return

        proj = runtime_config.projects.get(self.project_id)
        trigger = int(getattr(proj, "memory_compact_trigger_chars", 200000) if proj else 200000)
        keep = int(getattr(proj, "memory_compact_keep_chars", 50000) if proj else 50000)
        trigger = max(20000, trigger)
        keep = max(5000, min(keep, trigger - 1000))

        content = mem_path.read_text(encoding="utf-8")
        if len(content) <= trigger:
            return
        seed_block, body = self._split_seed_block(content)
        if len(body) <= trigger:
            return

        old = body[:-keep]
        recent = body[-keep:]
        action_names = re.findall(r"\[\[ACTION\]\]\s+([a-z_]+)\s+->", old)
        action_count = {}
        for name in action_names:
            action_count[name] = action_count.get(name, 0) + 1
        top_actions = sorted(action_count.items(), key=lambda x: x[1], reverse=True)[:8]
        top_text = ", ".join([f"{k}:{v}" for k, v in top_actions]) if top_actions else "none"

        archived_entries = old.count("### 📖 Entry")
        compact_note = (
            "# MEMORY_COMPACTED\n"
            f"Archived entries: {archived_entries}\n"
            f"Archived chars: {len(old)}\n"
            f"Top actions: {top_text}\n"
            "Old content moved to memory_archive.md\n\n"
            "---\n"
        )

        archive_path = self.agent_dir / "memory_archive.md"
        with open(archive_path, "a", encoding="utf-8") as af:
            af.write(old)
            if not old.endswith("\n"):
                af.write("\n")
            af.write("\n---\n")

        mem_path.write_text(seed_block + compact_note + recent, encoding="utf-8")

    def _split_seed_block(self, content: str):
        """
        Keep SYSTEM_SEED at the top across compaction.
        Returns (seed_block, body_without_seed).
        """
        marker = "### SYSTEM_SEED"
        if not content.startswith(marker):
            return "", content
        end = content.find("\n---\n")
        if end == -1:
            return "", content
        end += len("\n---\n")
        return content[:end], content[end:]

    def execute_tool(self, name: str, args: dict) -> str:
        """Execute the tool function with identity and project injection"""
        path_aware_tools = {
            "read_file",
            "write_file",
            "replace_content",
            "insert_content",
            "multi_replace",
            "list_dir",
            "run_command",
        }

        def ensure_cwd_prefix(msg: str) -> str:
            if not isinstance(msg, str):
                return str(msg)
            if "[Current CWD:" in msg:
                return msg
            return f"[Current CWD: {self.agent_dir.resolve()}] Content: {msg}"

        # Check if the tool is disabled for this agent in THIS project
        proj = runtime_config.projects.get(self.project_id)
        if proj:
            settings = proj.agent_settings.get(self.agent_id)
            if settings and name in settings.disabled_tools:
                return (
                    f"Divine Restriction: The tool '{name}' has been disabled for you by the High Overseer.\n"
                    "Suggested next step: choose another available tool aligned with your current phase."
                )

        args['caller_id'] = self.agent_id
        args['project_id'] = self.project_id
        for tool_func in self.get_tools():
            if tool_func.name == name:
                try:
                    result = tool_func.invoke(args)
                    if name in path_aware_tools:
                        result = ensure_cwd_prefix(result)
                    if name != "check_inbox":
                        reset_inbox_guard(self.agent_id, self.project_id)
                    return result
                except Exception as e:
                    return (
                        f"Tool Execution Error: failed to run '{name}'. Reason: {str(e)}\n"
                        "Suggested next step: verify required arguments and retry once."
                    )
        available = ", ".join([t.name for t in self.get_tools()])
        return (
            f"Tool Error: Unknown tool '{name}'.\n"
            f"Suggested next step: choose one from [{available}]."
        )

    def get_tools(self):
        return GODS_TOOLS

    def build_context(
        self,
        state: GodsState,
        directives: str,
        local_memory: str,
        inbox_content: str = "[]",
        phase_block: str = "",
        phase_name: str = "",
    ) -> str:
        """Autonomous Context Architecture with Project Awareness"""
        sacred_record = state.get("summary", "No ancient records.")
        recent_messages = state.get("messages", [])[-8:]
        history = "\n".join([
            f"[{getattr(msg, 'name', 'system')}]: {str(getattr(msg, 'content', ''))}"
            for msg in recent_messages
        ])
        
        tools_desc = "\n".join([f"- [[{t.name}({', '.join(t.args)})]]: {t.description}" for t in self.get_tools()])
        
        return prompt_registry.render(
            "agent_context",
            project_id=self.project_id,
            directives=directives,
            inbox_content=inbox_content,
            local_memory=local_memory,
            sacred_record=sacred_record,
            history=history,
            task=state.get("context", "Exist and evolve."),
            tools_desc=tools_desc,
            agent_id=self.agent_id,
            phase_block=phase_block,
            phase_name=phase_name,
        )

# Factory function for LangGraph nodes
def create_god_node(agent_id: str):
    def node_func(state: GodsState) -> GodsState:
        project_id = state.get("project_id", runtime_config.current_project)
        
        # Check if this agent chose to abstain from this thread
        abstained_list = state.get("abstained", [])
        if agent_id in abstained_list:
            print(f"[{agent_id}] Abstained from this Synod. Skipping...")
            state["next_step"] = "finish" # Handover to next
            return state

        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        return agent.process(state)
    return node_func

# Forward compatibility for existing hardcoded node names
def genesis_node(state: GodsState) -> GodsState:
    return create_god_node("genesis")(state)

def coder_node(state: GodsState) -> GodsState:
    return create_god_node("coder")(state)
