from __future__ import annotations

from gods.metis.strategy_specs import (
    export_strategy_default_tools,
    export_strategy_phase_map,
    get_strategy_spec,
)


def test_metis_strategy_specs_global_phase():
    phase_map = export_strategy_phase_map()
    assert phase_map["react_graph"] == ["global"]
    assert phase_map["freeform"] == ["global"]


def test_metis_default_tools_available():
    defaults = export_strategy_default_tools()
    assert defaults["react_graph"]["global"]


def test_metis_fallback_strategy():
    spec = get_strategy_spec("unknown")
    assert spec.strategy_id == "react_graph"
