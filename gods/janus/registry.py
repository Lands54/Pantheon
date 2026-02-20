"""Janus strategy registry."""
from __future__ import annotations

from typing import Any

from gods.janus.strategy_base import ContextStrategy
from gods.janus.strategies.sequential_v1 import SequentialV1Strategy

DEFAULT_CONTEXT_STRATEGY = "sequential_v1"

_STRATEGIES: dict[str, Any] = {
    DEFAULT_CONTEXT_STRATEGY: SequentialV1Strategy(),
}


def register_strategy(name: str, strategy: ContextStrategy) -> None:
    key = str(name or "").strip()
    if not key:
        raise ValueError("strategy name is required")
    _STRATEGIES[key] = strategy


def get_strategy(name: str) -> ContextStrategy:
    return _STRATEGIES.get(str(name or "").strip(), _STRATEGIES[DEFAULT_CONTEXT_STRATEGY])


def list_strategies() -> list[str]:
    return sorted(_STRATEGIES.keys())
