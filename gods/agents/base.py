"""
Gods Platform - Agent Node Definitions
Agents load their core logic directly from their respective agents/{id}/agent.md files.
"""
import uuid
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from gods.state import GodsState
from gods.agents.brain import GodBrain
from gods.tools import GODS_TOOLS
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
        """Autonomous Agent Pulse: Prioritize inbox, then work, then escalate."""
        max_tool_rounds = 4
        loop_key = f"_tool_loop_count_{self.agent_id}"
        current_loops = int(state.get(loop_key, 0))
        if current_loops >= max_tool_rounds:
            self._append_to_memory("Reached tool loop budget in this pulse. Yielding to other beings.")
            state[loop_key] = 0
            state["next_step"] = "finish"
            return state

        # 1. Automatic Inbox Perception (still injected for deterministic social awareness)
        inbox_msgs = self.execute_tool("check_inbox", {})
        
        # 2. Load context
        local_memory = self._load_local_memory()
        
        # 3. Enhance directives for social behavior
        simulation_directives = f"""
{self.directives}

# SOCIAL PROTOCOL
- You are an AVATAR in a shared world.
- You have a personal TERRITORY (agents/{self.agent_id}/).
- PRIORITIZE private messages (Inbox) to resolve conflicts.
- WORK independently in your territory whenever possible.
- ESCALATE to the Public Synod ONLY if private negotiation fails.
- ABSTAIN from Public Synod threads using [[abstain_from_synod]] if the topic is irrelevant to you.
"""
        context = self.build_context(state, simulation_directives, local_memory, inbox_msgs)
        
        print(f"[{self.agent_id}] Pulsing (Self-Aware Thinking)...")
        llm_messages = [SystemMessage(content=context)] + state.get("messages", [])[-8:]
        response = self.brain.think_with_tools(llm_messages, GODS_TOOLS)

        # Record thought and notify memory.md
        state["messages"].append(response)
        self._append_to_memory(response.content or "[No textual response]")

        # 4. Structured Tool Execution (official tool-calling path)
        tool_calls = getattr(response, "tool_calls", []) or []
        if tool_calls:
            for call in tool_calls:
                tool_name = call.get("name", "")
                args = call.get("args", {}) if isinstance(call.get("args", {}), dict) else {}
                tool_call_id = call.get("id") or f"{tool_name}_{uuid.uuid4().hex[:8]}"

                obs = self.execute_tool(tool_name, args)
                state["messages"].append(
                    ToolMessage(content=obs, tool_call_id=tool_call_id, name=tool_name)
                )
                self._append_to_memory(f"[[ACTION]] {tool_name} -> {obs}")
                
                # Special: If escalated, stop pulse and flag for global resonance
                if tool_name == "post_to_synod":
                    state[loop_key] = 0
                    state["next_step"] = "escalated"
                    return state
                
                # Special: If abstained, mark as disinterested in this thread
                if tool_name == "abstain_from_synod":
                    if "abstained" not in state or state["abstained"] is None:
                        state["abstained"] = []
                    if self.agent_id not in state["abstained"]:
                        state["abstained"].append(self.agent_id)
                    state[loop_key] = 0
                    state["next_step"] = "abstained"
                    return state
            
            state[loop_key] = current_loops + 1
            state["next_step"] = "continue"
        else:
            state[loop_key] = 0
            state["next_step"] = "finish"
            
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
                    return tool_func.invoke(args)
                except Exception as e:
                    return f"Error executing {name}: {str(e)}"
        return f"Unknown tool: {name}"

    def build_context(self, state: GodsState, directives: str, local_memory: str, inbox_content: str = "[]") -> str:
        """Autonomous Context Architecture with Project Awareness"""
        sacred_record = state.get("summary", "No ancient records.")
        recent_messages = state.get("messages", [])[-5:]
        history = "\n".join([f"[{getattr(msg, 'name', 'system')}]: {msg.content}" for msg in recent_messages])
        
        tools_desc = "\n".join([f"- [[{t.name}({', '.join(t.args)})]]: {t.description}" for t in GODS_TOOLS])
        
        context = f"""
# IDENTITY
{directives}
Project: {self.project_id}

# SACRED INBOX (Incoming Private Revelations)
{inbox_content}

# YOUR CHRONICLES (memory.md)
{local_memory}

# TERRITORY
Location: projects/{self.project_id}/agents/{self.agent_id}/

# GLOBAL RECORD & SYNOD HISTORY
{sacred_record}
{history}

# TASK (Current Universal Intent)
{state.get('context', 'Exist and evolve.')}

# AVAILABLE TOOLS
{tools_desc}

# PROTOCOL
1. Read your inbox FIRST.
2. If another Being reached out, reply via tool calling (send_message).
3. Carry out your work via structured tool calls only.
4. Do NOT emit custom wrappers like [[...]] or <tool_call>...</tool_call>.
5. If stuck, use post_to_synod.
"""
        return context

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
