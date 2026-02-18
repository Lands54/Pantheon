from __future__ import annotations

from gods.agents.orchestrators.nike import NikeOrchestrator


class _FakeProject:
    agent_id = "a"
    project_id = "p"


def test_nike_keeps_finalize_bridge(monkeypatch):
    monkeypatch.setattr(
        "gods.agents.orchestrators.nike.run_agent_runtime",
        lambda _project, state: {**state, "next_step": "finish", "finalize_control": {"mode": "quiescent"}},
    )
    out = NikeOrchestrator.run(_FakeProject(), {"messages": []})
    assert out.get("__finalize_control", {}).get("mode") == "quiescent"
