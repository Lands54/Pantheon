"""Freeform graph strategy built on same runtime nodes."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from gods.agents.runtime.models import RuntimeState
from gods.agents.runtime.nodes import (
    build_context_node,
    decide_next_node,
    dispatch_tools_node,
    llm_think_node,
)


def build_freeform_graph(agent):
    graph = StateGraph(RuntimeState)
    graph.add_node("build_context", lambda s: build_context_node(agent, s))
    graph.add_node("llm_think", lambda s: llm_think_node(agent, s))
    graph.add_node("dispatch_tools", lambda s: dispatch_tools_node(agent, s))
    graph.add_node("decide_next", lambda s: decide_next_node(agent, s))

    graph.add_edge(START, "build_context")
    graph.add_edge("build_context", "llm_think")
    graph.add_edge("llm_think", "dispatch_tools")
    graph.add_edge("dispatch_tools", "decide_next")
    graph.add_conditional_edges(
        "decide_next",
        lambda s: str(s.get("route", "done")),
        {
            "again": "build_context",
            "done": END,
        },
    )
    return graph.compile()
