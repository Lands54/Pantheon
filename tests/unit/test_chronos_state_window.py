from __future__ import annotations

from gods.agents.orchestrators.chronos import ChronosOrchestrator


def test_chronos_merge_finalize_noop_without_state_window():
    state = {}
    ChronosOrchestrator.merge("p", "a", state)
    assert state.get("messages") == []

    out = ChronosOrchestrator.finalize("p", "a", state)
    assert out is state
