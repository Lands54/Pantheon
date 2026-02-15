"""Janus strategy registry."""
from __future__ import annotations

from gods.janus.strategy_base import ContextStrategy
from gods.janus.strategies.structured_v1 import StructuredV1ContextStrategy


_STRATEGIES: dict[str, ContextStrategy] = {
    "structured_v1": StructuredV1ContextStrategy(),
}


def get_strategy(name: str) -> ContextStrategy:
    return _STRATEGIES.get(str(name or "").strip(), _STRATEGIES["structured_v1"])


def list_strategies() -> list[str]:
    return sorted(_STRATEGIES.keys())
