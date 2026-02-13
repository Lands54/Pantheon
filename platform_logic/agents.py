"""
Gods Platform - Agent Node Definitions
Agents load their core logic directly from their respective agents/{id}/agent.md files.
"""
from langchain_core.messages import HumanMessage, AIMessage
from gods_platform.graph_state import GodsState
from platform_logic.brain import GodBrain
from platform_logic.tools import GODS_TOOLS
from gods_platform.config import runtime_config
from pathlib import Path
import re


class GodAgent:
    """
    Dynamic Agent that derives identity and behavior from filesystem metadata.
    Source of truth: agents/{agent_id}/agent.md
    """
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.agent_dir = Path(f"agents/{agent_id}")
        self.agent_md = self.agent_dir / "agent.md"
        
        # Load behavior description from agent.md
        self.directives = self._load_directives()
        
        # Initialize brain with specific settings from config
        self.brain = GodBrain(agent_id=agent_id)

    def _load_directives(self) -> str:
        """Load the core mission/logic from agent.md"""
        if self.agent_md.exists():
            return self.agent_md.read_text(encoding="utf-8")
        return f"Agent ID: {self.agent_id}\n(No agent.md found. Please create one in {self.agent_md})"
    
    def process(self, state: GodsState) -> GodsState:
        """Process a single ReAct step for the agent"""
        # Construction of the prompt context
        context = self.build_context(state, self.directives)
        
        print(f"[{self.agent_id}] Processing...")
        response = self.brain.think(context)
        
        # Record thought
        new_message = AIMessage(content=response, name=self.agent_id)
        state["messages"].append(new_message)
        state["current_speaker"] = self.agent_id
        
        # ReAct loop control: Check for tool calls
        tool_calls = self.parse_tool_calls(response)
        
        if tool_calls:
            observations = []
            for tool_name, args in tool_calls:
                print(f"[{self.agent_id}] Invoking tool: {tool_name}")
                obs = self.execute_tool(tool_name, args)
                observations.append(f"Observation from {tool_name}: {obs}")
            
            # Feed observations back as system feedback
            obs_content = "\n".join(observations)
            state["messages"].append(HumanMessage(content=obs_content, name="system"))
            state["next_step"] = "continue"
        else:
            state["next_step"] = "finish"
            
        return state

    def parse_tool_calls(self, text: str) -> list:
        """Parse [[tool_name(key=\"val\")]] matches"""
        pattern = r"\[\[(\w+)\((.*?)\)\]\]"
        matches = re.findall(pattern, text)
        results = []
        for name, args_str in matches:
            args = {}
            kv_pattern = r'(\w+)\s*=\s*"(.*?)"'
            for k, v in re.findall(kv_pattern, args_str):
                args[k] = v
            results.append((name, args))
        return results

    def execute_tool(self, name: str, args: dict) -> str:
        """Execute the tool function"""
        for tool_func in GODS_TOOLS:
            if tool_func.name == name:
                try:
                    return tool_func.invoke(args)
                except Exception as e:
                    return f"Error executing {name}: {str(e)}"
        return f"Unknown tool: {name}"
    
    def build_context(self, state: GodsState, directives: str) -> str:
        """Build the full inference prompt"""
        recent_messages = state.get("messages", [])[-10:]
        history = "\n".join([
            f"[{getattr(msg, 'name', 'system')}]: {msg.content}" 
            for msg in recent_messages
        ])
        
        initial_mission = state.get("context", "No task assigned.")
        tools_desc = "\n".join([f"- [[{t.name}({', '.join(t.args)})]]: {t.description}" for t in GODS_TOOLS])
        
        context = f"""# IDENTITY AND DIRECTIVES
{directives}

# MISSION
{initial_mission}

# AVAILABLE TOOLS (ReAct Protocol)
Use format: [[tool_name(arg_name="value")]]
{tools_desc}

# CONTEXT HISTORY
{history}

# TASK
Based on your directives and current state, decide the next move. 
If you need information, use a tool. 
ALWAYS end your thinking with a tool call if action is needed, otherwise provide a final response.
"""
        return context

# Factory function for LangGraph nodes
def create_god_node(agent_id: str):
    def node_func(state: GodsState) -> GodsState:
        agent = GodAgent(agent_id=agent_id)
        return agent.process(state)
    return node_func

# Forward compatibility for existing hardcoded node names
def genesis_node(state: GodsState) -> GodsState:
    return create_god_node("genesis")(state)

def coder_node(state: GodsState) -> GodsState:
    return create_god_node("coder")(state)
