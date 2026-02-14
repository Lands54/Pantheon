"""
Gods Platform - Agent Node Definitions
Agents load their core logic directly from their respective agents/{id}/agent.md files.
"""
import uuid
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from gods.state import GodsState
from gods.agents.brain import GodBrain
from gods.prompts import prompt_registry
from gods.tools import GODS_TOOLS
from gods.tools.communication import reset_inbox_guard
from gods.config import runtime_config
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
        
        # Initialize brain with specific settings from config
        self.brain = GodBrain(agent_id=agent_id, project_id=project_id)

    def _load_directives(self) -> str:
        """Load the core mission/logic from agent.md"""
        if self.agent_md.exists():
            return self.agent_md.read_text(encoding="utf-8")
        return f"Agent ID: {self.agent_id}\n(No agent.md found. Please create one in {self.agent_md})"
    
    def process(self, state: GodsState) -> GodsState:
        """Autonomous Agent Pulse: run model<->tool loop until no tool calls."""
        proj = runtime_config.projects.get(self.project_id)
        max_tool_rounds = int(getattr(proj, "tool_loop_max", 8) if proj else 8)
        max_tool_rounds = max(1, min(max_tool_rounds, 64))
        inbox_msgs = "Inbox is not pre-fetched. Use check_inbox tool when needed."
        local_memory = self._load_local_memory()
        simulation_directives = prompt_registry.render(
            "agent_social_protocol",
            project_id=self.project_id,
            directives=self.directives,
            agent_id=self.agent_id,
        )

        print(f"[{self.agent_id}] Pulsing (Self-Aware Thinking)...")

        for _ in range(max_tool_rounds):
            context = self.build_context(state, simulation_directives, local_memory, inbox_msgs)
            llm_messages = [SystemMessage(content=context)] + state.get("messages", [])[-16:]
            response = self.brain.think_with_tools(llm_messages, GODS_TOOLS)

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
        """Load the tail of memory.md for contextual awareness"""
        mem_path = self.agent_dir / "memory.md"
        if mem_path.exists():
            content = mem_path.read_text(encoding="utf-8")
            return content[-1500:] if len(content) > 1500 else content
        return "No personal chronicles yet."

    def _append_to_memory(self, text: str):
        """Append a thought or event to the human-readable memory.md"""
        from datetime import datetime
        mem_path = self.agent_dir / "memory.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n### 📖 Entry [{timestamp}]\n{text}\n\n---\n"
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def execute_tool(self, name: str, args: dict) -> str:
        """Execute the tool function with identity and project injection"""
        # Check if the tool is disabled for this agent in THIS project
        proj = runtime_config.projects.get(self.project_id)
        if proj:
            settings = proj.agent_settings.get(self.agent_id)
            if settings and name in settings.disabled_tools:
                return f"Divine Restriction: The tool '{name}' has been disabled for you by the High Overseer."

        args['caller_id'] = self.agent_id
        args['project_id'] = self.project_id
        for tool_func in GODS_TOOLS:
            if tool_func.name == name:
                try:
                    result = tool_func.invoke(args)
                    if name != "check_inbox":
                        reset_inbox_guard(self.agent_id, self.project_id)
                    return result
                except Exception as e:
                    return f"Error executing {name}: {str(e)}"
        return f"Unknown tool: {name}"

    def build_context(self, state: GodsState, directives: str, local_memory: str, inbox_content: str = "[]") -> str:
        """Autonomous Context Architecture with Project Awareness"""
        sacred_record = state.get("summary", "No ancient records.")
        recent_messages = state.get("messages", [])[-5:]
        history = "\n".join([f"[{getattr(msg, 'name', 'system')}]: {msg.content}" for msg in recent_messages])
        
        tools_desc = "\n".join([f"- [[{t.name}({', '.join(t.args)})]]: {t.description}" for t in GODS_TOOLS])
        
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
