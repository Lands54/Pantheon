"""Gods Platform - Agent Node Definitions."""
import re
import time
from gods.state import GodsState
from gods.agents.brain import GodBrain
from gods.tools import GODS_TOOLS
from gods.tools.communication import reset_inbox_guard
from gods.config import runtime_config
from gods.mnemosyne import MemoryIntent, record_intent
from gods.mnemosyne.intent_builders import intent_from_tool_result
from gods.agents.runtime import run_agent_runtime
from gods.agents.tool_policy import is_social_disabled, is_tool_disabled
from gods.paths import agent_dir, mnemosyne_dir
from gods.janus import record_observation, ObservationRecord
from gods.janus.journal import profile_path
from gods.agents.state_window_store import load_state_window, save_state_window
from pathlib import Path


class GodAgent:
    """
    Dynamic Agent that derives identity and behavior from filesystem metadata.
    Source of truth: projects/{project_id}/mnemosyne/agent_profiles/{agent_id}.md
    """
    def __init__(self, agent_id: str, project_id: str = "default"):
        """
        Initializes a new GodAgent instance.
        """
        self.agent_id = agent_id
        self.project_id = project_id
        self.agent_dir = agent_dir(project_id, agent_id)

        # Load behavior description from Mnemosyne profile only.
        self.directives = self._load_directives()
        self._ensure_memory_seeded()
        
        # Initialize brain with specific settings from config
        self.brain = GodBrain(agent_id=agent_id, project_id=project_id)

    def _load_directives(self) -> str:
        """
        Loads the core mission and logic from Mnemosyne profile.
        """
        p = profile_path(self.project_id, self.agent_id)
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8").strip()
                if text:
                    return text
            except Exception:
                pass
        return (
            f"Agent ID: {self.agent_id}\n"
            "No Mnemosyne profile found. Write directives to "
            f"projects/{self.project_id}/mnemosyne/agent_profiles/{self.agent_id}.md"
        )

    def _chronicle_path(self) -> Path:
        return mnemosyne_dir(self.project_id) / "chronicles" / f"{self.agent_id}.md"

    def _ensure_memory_seeded(self):
        """
        Seeds Mnemosyne chronicle with a directives snapshot if empty.
        """
        mem_path = self._chronicle_path()
        if mem_path.exists():
            try:
                if mem_path.stat().st_size > 0:
                    return
            except Exception:
                return
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        seed = (
            "### SYSTEM_SEED\n"
            "Directives snapshot (from Mnemosyne profile):\n\n"
            f"{self.directives}\n\n---\n"
        )
        mem_path.write_text(seed, encoding="utf-8")
    
    def _build_inbox_context_hint(self) -> str:
        """
        Constructs a hint for the agent about its inbox accessibility.
        """
        if is_tool_disabled(self.project_id, self.agent_id, "check_inbox"):
            return (
                "Inbox events are pre-injected by scheduler. "
                "check_inbox is disabled by policy (debug fallback only)."
            )
        return "Inbox events are pre-injected by scheduler. Use check_inbox only for audit fallback."

    def _build_behavior_directives(self) -> str:
        """
        Builds the behavioral directives for the agent, accounting for social tool restrictions.
        """
        if is_social_disabled(self.project_id, self.agent_id):
            return (
                "# LOCAL EXECUTION PROTOCOL\n"
                "- Social tools are disabled for this agent.\n"
                "- Do NOT attempt inbox/social actions.\n"
                "- Focus only on local implementation, verification, and completion."
            )
        # Standard protocol is now implicit or handled by context strategy; 
        # return empty or specific overrides if needed.
        # For now, we return a simple placeholder or rely on system prompt.
        return ""

    def process(self, state: GodsState) -> GodsState:
        """
        Main execution loop for the agent via unified LangGraph runtime.
        """
        self._merge_state_window_if_needed(state)
        out = run_agent_runtime(self, state)
        return self._return_with_state_window(out)

    def _merge_state_window_if_needed(self, state: GodsState):
        try:
            if not isinstance(state, dict):
                return
            if bool(state.get("__state_window_loaded", False)):
                return
            loaded = load_state_window(self.project_id, self.agent_id)
            current = list(state.get("messages", []) or [])
            if loaded:
                state["messages"] = loaded + current
            else:
                state.setdefault("messages", current)
            state["__state_window_loaded"] = True
        except Exception:
            pass

    def _persist_state_window(self, state: GodsState):
        try:
            if not isinstance(state, dict):
                return
            msgs = list(state.get("messages", []) or [])
            if not msgs:
                return
            save_state_window(self.project_id, self.agent_id, msgs)
        except Exception:
            pass

    def _return_with_state_window(self, state: GodsState) -> GodsState:
        self._persist_state_window(state)
        return state

    def _load_local_memory(self) -> str:
        """
        Loads local memory chronicle from Mnemosyne.
        """
        mem_path = self._chronicle_path()
        if mem_path.exists():
            return mem_path.read_text(encoding="utf-8")
        return "No personal chronicles yet."

    def _record_intent(self, intent: MemoryIntent):
        return record_intent(intent)

    @staticmethod
    def _is_transient_llm_error_text(text: str) -> bool:
        raw = str(text or "").strip().lower()
        return raw.startswith("error in reasoning:") or raw.startswith("❌ error:")

    @staticmethod
    def _classify_tool_status(result: str) -> str:
        text = str(result or "").strip()
        # Strip common CWD wrappers before classification.
        norm = re.sub(r"^\[Current CWD:[^\]]+\]\s*", "", text, flags=re.I).strip()
        if norm.lower().startswith("content:"):
            norm = norm[len("content:") :].strip()
        low = norm.lower()

        if "divine restriction" in low or "policy block" in low:
            return "blocked"

        error_prefixes = (
            "tool execution error:",
            "tool error:",
            "path error:",
            "execution failed:",
            "execution timeout:",
            "execution backend error:",
            "territory error:",
            "command error:",
            "concurrency limit:",
        )
        if low.startswith(error_prefixes):
            return "error"

        m = re.search(r"manifestation result \(exit=(-?\d+)\):", low)
        if m:
            try:
                return "ok" if int(m.group(1)) == 0 else "error"
            except Exception:
                return "error"

        return "ok"

    @staticmethod
    def _finalize_control_from_args(args: dict) -> dict:
        raw = dict(args or {})
        mode = str(raw.get("mode", "done") or "done").strip().lower()
        if mode not in {"done", "quiescent"}:
            mode = "done"
        try:
            sleep_sec = int(raw.get("sleep_sec", 0) or 0)
        except Exception:
            sleep_sec = 0
        return {
            "mode": mode,
            "sleep_sec": sleep_sec,
            "reason": str(raw.get("reason", "") or ""),
        }

    def execute_tool(self, name: str, args: dict) -> str:
        """
        Executes a specific tool by name, handling project and agent identity context.
        """
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
                blocked = (
                    f"Divine Restriction: The tool '{name}' has been disabled for you by the High Overseer.\n"
                    "Suggested next step: choose another available tool aligned with your current phase."
                )
                self._record_observation(name, args, blocked, status="blocked")
                self._record_intent(intent_from_tool_result(self.project_id, self.agent_id, name, "blocked", args, blocked))
                return blocked

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
                    status = self._classify_tool_status(str(result))
                    self._record_observation(name, args, result, status=status)
                    self._record_intent(intent_from_tool_result(self.project_id, self.agent_id, name, status, args, str(result)))
                    return result
                except Exception as e:
                    err = (
                        f"Tool Execution Error: failed to run '{name}'. Reason: {str(e)}\n"
                        "Suggested next step: verify required arguments and retry once."
                    )
                    self._record_observation(name, args, err, status="error")
                    self._record_intent(intent_from_tool_result(self.project_id, self.agent_id, name, "error", args, err))
                    return err
        available = ", ".join([t.name for t in self.get_tools()])
        unknown = (
            f"Tool Error: Unknown tool '{name}'.\n"
            f"Suggested next step: choose one from [{available}]."
        )
        self._record_observation(name, args, unknown, status="error")
        self._record_intent(intent_from_tool_result(self.project_id, self.agent_id, name, "error", args, unknown))
        return unknown

    def _record_observation(self, name: str, args: dict, result: str, status: str):
        try:
            args_summary = str(args)[:240]
            result_summary = str(result)[:500]
            record_observation(
                ObservationRecord(
                    project_id=self.project_id,
                    agent_id=self.agent_id,
                    tool_name=name,
                    args_summary=args_summary,
                    result_summary=result_summary,
                    status=status,
                    timestamp=time.time(),
                )
            )
        except Exception:
            pass

    def get_tools(self):
        """
        Returns the list of tools available to this agent.
        """
        disabled: set[str] = set()
        proj = runtime_config.projects.get(self.project_id)
        if proj:
            settings = proj.agent_settings.get(self.agent_id)
            if settings:
                disabled = set(settings.disabled_tools or [])
        return [t for t in GODS_TOOLS if t.name not in disabled]

    def _render_tools_desc(self) -> str:
        items = []
        for t in self.get_tools():
            items.append(f"- [[{t.name}({', '.join(t.args)})]]: {t.description}")
        return "\n".join(items)

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
            state["next_step"] = "finish" # Handover to next
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
