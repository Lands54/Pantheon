"""Runtime strategy registry."""
from __future__ import annotations

from typing import Callable

from langgraph.graph.state import CompiledStateGraph


GraphBuilder = Callable[[object], CompiledStateGraph]
_REGISTRY: dict[str, GraphBuilder] = {}


def register_strategy(name: str, builder: GraphBuilder) -> None:
    key = str(name or "").strip().lower()
    if not key:
        raise ValueError("strategy name is required")
    _REGISTRY[key] = builder


def get_strategy_builder(name: str) -> GraphBuilder:
    key = str(name or "").strip().lower()
    if key not in _REGISTRY:
        raise ValueError(f"unsupported runtime strategy: {name}")
    return _REGISTRY[key]


def list_strategies() -> list[str]:
    return sorted(_REGISTRY.keys())
