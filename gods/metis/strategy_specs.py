"""Built-in Metis strategy specifications."""
from __future__ import annotations

from gods.metis.contracts import StrategySpec
from gods.tools import available_tool_names


_GLOBAL_DEFAULT_TOOLS = available_tool_names()

_SPECS: dict[str, StrategySpec] = {
    "react_graph": StrategySpec(
        strategy_id="react_graph",
        phases=["global"],
        default_tool_policies={"global": list(_GLOBAL_DEFAULT_TOOLS)},
        required_resources=["events", "mailbox", "memory", "tool_catalog", "config_view"],
        node_order=["build_context", "llm_think", "dispatch_tools", "decide_next"],
    ),
    "freeform": StrategySpec(
        strategy_id="freeform",
        phases=["global"],
        default_tool_policies={"global": list(_GLOBAL_DEFAULT_TOOLS)},
        required_resources=["events", "mailbox", "memory", "tool_catalog", "config_view"],
        node_order=["build_context", "llm_think", "dispatch_tools", "decide_next"],
    ),
}


def get_strategy_spec(strategy_id: str) -> StrategySpec:
    sid = str(strategy_id or "").strip().lower()
    return _SPECS.get(sid, _SPECS["react_graph"])


def list_strategy_specs() -> list[StrategySpec]:
    return [v for _, v in sorted(_SPECS.items(), key=lambda x: x[0])]


def export_strategy_phase_map() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for spec in list_strategy_specs():
        out[spec.strategy_id] = list(spec.phases)
    return out


def export_strategy_default_tools() -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for spec in list_strategy_specs():
        out[spec.strategy_id] = {
            phase: list(tools) for phase, tools in (spec.default_tool_policies or {}).items()
        }
    return out
