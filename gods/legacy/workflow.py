"""
Legacy LangGraph workflow engine (broadcast/private routes).
Not used by the autonomous scheduler core path.
"""
import sqlite3
from pathlib import Path
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from gods.state import GodsState
from gods.config import runtime_config
from gods.agents.base import create_god_node
from gods.agents.brain import GodBrain
from gods.prompts import prompt_registry
from langchain_core.messages import RemoveMessage


def should_continue(state: GodsState) -> str:
    """Decide between continuing the current Agent's ReAct loop or handing over."""
    if state.get("next_step") == "continue":
        return "loop"
    return "next"


def summarize_conversation(state: GodsState):
    """
    Summarize the conversation if it grows too long.
    Uses dynamic threshold and keep count from the associated project config.
    """
    project_id = state.get("project_id", "default")
    proj = runtime_config.projects.get(project_id)
    threshold = proj.summarize_threshold if proj else 12
    keep_count = proj.summarize_keep_count if proj else 5

    messages = state["messages"]
    if len(messages) <= threshold:
        return state

    print(f"[{project_id}] --- SUMMARIZING CONVERSATION ---")

    brain = GodBrain(agent_id="system_mnemosyne", project_id=project_id)
    existing_summary = state.get("summary", "")
    to_summarize = messages[:-keep_count]
    history_str = "\n".join([f"{msg.name if hasattr(msg, 'name') else 'user'}: {msg.content}" for msg in to_summarize])

    prompt = prompt_registry.render(
        "workflow_summarizer",
        project_id=project_id,
        existing_summary=existing_summary,
        history_str=history_str,
    )
    new_summary = brain.think(prompt)
    delete_messages = [RemoveMessage(id=m.id) for m in to_summarize if hasattr(m, 'id')]

    return {"summary": new_summary, "messages": delete_messages}


def create_gods_workflow(project_id: str = "default"):
    """Create the orchestrated debate workflow for a specific project."""
    workflow = StateGraph(GodsState)

    proj = runtime_config.projects.get(project_id)
    active_ids = proj.active_agents if proj else ["genesis"]

    for agent_id in active_ids:
        workflow.add_node(agent_id, create_god_node(agent_id))

    workflow.add_node("summarizer", summarize_conversation)
    workflow.set_entry_point(active_ids[0])

    for i in range(len(active_ids)):
        current_id = active_ids[i]
        next_target = active_ids[i + 1] if i + 1 < len(active_ids) else "summarizer"
        workflow.add_conditional_edges(current_id, should_continue, {"loop": current_id, "next": next_target})

    workflow.add_edge("summarizer", END)

    db_dir = Path("projects") / project_id
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_dir / "memory.sqlite", check_same_thread=False)
    memory = SqliteSaver(conn)
    return workflow.compile(checkpointer=memory)


def create_private_workflow(agent_id: str, project_id: str = "default"):
    """Create a private chat workflow for a specific project."""
    workflow = StateGraph(GodsState)
    workflow.add_node(agent_id, create_god_node(agent_id))
    workflow.add_node("summarizer", summarize_conversation)
    workflow.set_entry_point(agent_id)
    workflow.add_conditional_edges(agent_id, should_continue, {"loop": agent_id, "next": "summarizer"})
    workflow.add_edge("summarizer", END)

    db_dir = Path("projects") / project_id
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_dir / "memory.sqlite", check_same_thread=False)
    memory = SqliteSaver(conn)
    return workflow.compile(checkpointer=memory)

