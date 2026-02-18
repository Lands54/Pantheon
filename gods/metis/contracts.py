"""Metis contracts for strategy material injection."""
from __future__ import annotations

from dataclasses import dataclass, field

from gods.chaos.contracts import ResourceSnapshot


@dataclass
class RuntimeEnvelope:
    """Runtime envelope injected into graph state for stateless nodes."""

    strategy: str
    state: dict[str, Any]
    resource_snapshot: ResourceSnapshot
    policy: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategySpec:
    """Strategy-level contract for phases and default tool policies."""

    strategy_id: str
    phases: list[str]
    default_tool_policies: dict[str, list[str]]
    required_resources: list[str]
    node_order: list[str]
