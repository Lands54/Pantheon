from __future__ import annotations

from gods.mnemosyne import facade as mnemosyne_facade
from api.services.project_service import project_service
from gods.config import runtime_config, ProjectConfig


def test_no_pulse_split_under_tool_chain():
    project_id = "it_pulse_tool_chain"
    agent_id = "alpha"
    runtime_config.projects[project_id] = ProjectConfig()
    rows = [
        {"pulse_id": "p1", "kind": "pulse.start", "payload": {"reason": "manual"}, "origin": "angelia"},
        {"pulse_id": "p1", "kind": "trigger.event", "payload": {"event_type": "manual", "event_id": "e1"}, "origin": "angelia"},
        {"pulse_id": "p1", "kind": "llm.response", "payload": {"content": "ok"}, "origin": "internal"},
        {"pulse_id": "p1", "kind": "tool.call", "payload": {"tool_name": "list", "call_id": "c1", "args": {"path": "."}}, "origin": "internal"},
        {"pulse_id": "p1", "kind": "tool.result", "payload": {"tool_name": "list", "call_id": "c1", "status": "ok", "result": "ok"}, "origin": "internal"},
        {"pulse_id": "p1", "kind": "pulse.finish", "payload": {"next_step": "finish"}, "origin": "angelia"},
    ]
    mnemosyne_facade.append_pulse_entries(project_id, agent_id, rows)
    out = project_service.context_pulses(project_id, agent_id, from_seq=0, limit=200)
    assert int(out.get("count", 0) or 0) >= 1
    pulses = list(out.get("pulses", []) or [])
    p1 = None
    for p in pulses:
        if str(p.get("pulse_id", "")) == "p1":
            p1 = p
            break
    assert p1 is not None
    assert len(list(p1.get("tools", []) or [])) >= 2
