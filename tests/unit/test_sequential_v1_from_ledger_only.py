from __future__ import annotations

from types import SimpleNamespace

import pytest

from gods.janus.facade import ContextBuildRequest, SequentialV1Strategy


def test_sequential_v1_builds_from_ledger_frames_only(monkeypatch):
    strategy = SequentialV1Strategy()

    def _load(*_args, **_kwargs):
        fr = SimpleNamespace(pulse_id="p1", timestamp=1.0, triggers=[], agent_response=SimpleNamespace(text="", tool_calls=[]))
        fr.triggers = [SimpleNamespace(kind="event", origin="internal", item_type="manual", item_id="e1", title="", sender="", content="manual")]
        fr.agent_response.text = "hello"
        return [fr], []

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)

    req = ContextBuildRequest(
        project_id="p",
        agent_id="a",
        state={},
        directives="dir",
        local_memory="",
        inbox_hint="hint",
        tools_desc="tool-desc",
        context_cfg={},
        context_materials=SimpleNamespace(profile="profile", directives="d", task_state="task", tools="tools", inbox_hint="hint"),
    )
    out = strategy.build(req)
    blob = "\n".join(out.system_blocks)
    assert "<pulse id=\"p1\" state=\"processing\">" in blob
    assert "<trigger>" in blob
    assert "hello" in blob


def test_sequential_v1_empty_trigger_pulse_hard_fail(monkeypatch):
    """Pulses with no triggers must fail under strict pulse contract."""
    strategy = SequentialV1Strategy()

    def _load(*_args, **_kwargs):
        # One bad pulse (no triggers) + one good pulse
        bad = SimpleNamespace(pulse_id="p_bad", timestamp=1.0, triggers=[], agent_response=SimpleNamespace(text="", tool_calls=[]))
        good = SimpleNamespace(pulse_id="p_good", timestamp=2.0, triggers=[], agent_response=SimpleNamespace(text="ok", tool_calls=[]))
        good.triggers = [SimpleNamespace(kind="event", origin="internal", item_type="system", item_id="e1", title="", sender="", content="project_started")]
        return [bad, good], []

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)

    req = ContextBuildRequest(
        project_id="p",
        agent_id="a",
        state={},
        directives="",
        local_memory="",
        inbox_hint="",
        tools_desc="",
        context_cfg={},
        context_materials=SimpleNamespace(profile="", directives="", task_state="", tools="", inbox_hint=""),
    )
    with pytest.raises(ValueError, match="PULSE_EMPTY_TRIGGER"):
        strategy.build(req)


def test_sequential_v1_integrity_errors_hard_fail(monkeypatch):
    """Integrity errors are fatal under strict pulse contract."""
    strategy = SequentialV1Strategy()

    def _load(*_args, **_kwargs):
        fr = SimpleNamespace(pulse_id="p1", timestamp=1.0, triggers=[], agent_response=SimpleNamespace(text="hello", tool_calls=[]))
        fr.triggers = [SimpleNamespace(kind="event", origin="internal", item_type="manual", item_id="e1", title="", sender="", content="manual")]
        return [fr], ["p_old: missing pulse.start"]

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)

    req = ContextBuildRequest(
        project_id="p",
        agent_id="a",
        state={},
        directives="",
        local_memory="",
        inbox_hint="",
        tools_desc="",
        context_cfg={},
        context_materials=SimpleNamespace(profile="", directives="", task_state="", tools="", inbox_hint=""),
    )
    with pytest.raises(ValueError, match="PULSE_INTEGRITY_ERROR"):
        strategy.build(req)
