from __future__ import annotations

from langchain_core.messages import HumanMessage

from gods.agents.orchestrators.chronos import ChronosOrchestrator


def test_chronos_merge_once_and_finalize(monkeypatch):
    loaded_messages = [HumanMessage(content="persisted")]
    saved: list = []

    monkeypatch.setattr("gods.agents.orchestrators.chronos.load_state_window", lambda _p, _a: loaded_messages)
    monkeypatch.setattr("gods.agents.orchestrators.chronos.save_state_window", lambda _p, _a, msgs: saved.append(list(msgs)))

    state = {"messages": [HumanMessage(content="current")]}
    ChronosOrchestrator.merge("p", "a", state)
    assert len(state["messages"]) == 2
    assert state.get("__state_window_loaded") is True

    ChronosOrchestrator.merge("p", "a", state)
    assert len(state["messages"]) == 2

    out = ChronosOrchestrator.finalize("p", "a", state)
    assert out is state
    assert saved and len(saved[-1]) == 2
