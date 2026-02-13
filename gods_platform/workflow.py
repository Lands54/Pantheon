"""
Gods Platform - Dynamic Workflow Engine
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from gods_platform.graph_state import GodsState
from gods_platform.config import runtime_config
from platform_logic.agents import create_god_node


def should_continue(state: GodsState) -> str:
    """Decide between continuing the current Agent's ReAct loop or handing over."""
    if state.get("next_step") == "continue":
        return "loop"
    return "next"


def create_gods_workflow():
    """Create the orchestrated debate workflow based on active_agents."""
    workflow = StateGraph(GodsState)
    
    active_ids = runtime_config.active_agents
    if not active_ids:
        active_ids = ["genesis"] # Fallback

    # 1. Add nodes
    for agent_id in active_ids:
        workflow.add_node(agent_id, create_god_node(agent_id))
    
    # 2. Set entry
    workflow.set_entry_point(active_ids[0])
    
    # 3. Dynamic edges
    for i in range(len(active_ids)):
        current_id = active_ids[i]
        next_id = active_ids[i+1] if i + 1 < len(active_ids) else END
        
        workflow.add_conditional_edges(
            current_id,
            should_continue,
            {
                "loop": current_id,
                "next": next_id
            }
        )
    
    return workflow.compile(checkpointer=MemorySaver())

def create_private_workflow(agent_id: str):
    """Create a single-agent memory-persistent workflow for private chats."""
    workflow = StateGraph(GodsState)
    workflow.add_node(agent_id, create_god_node(agent_id))
    workflow.set_entry_point(agent_id)
    
    workflow.add_conditional_edges(
        agent_id,
        should_continue,
        {
            "loop": agent_id,
            "next": END
        }
    )
    return workflow.compile(checkpointer=MemorySaver())
