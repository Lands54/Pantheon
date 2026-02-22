from __future__ import annotations

from types import SimpleNamespace
import pytest

from gods.janus import facade as janus_facade


def _req() -> janus_facade.ContextBuildRequest:
    return janus_facade.ContextBuildRequest(
        project_id="unit_seq",
        agent_id="alpha",
        state={},
        directives="",
        local_memory="",
        inbox_hint="",
        tools_desc="",
        context_cfg={},
        context_materials=SimpleNamespace(profile="", directives="", task_state="", tools="", inbox_hint=""),
    )


def test_build_fails_on_integrity_error(monkeypatch):
    """Integrity errors are fatal under strict pulse contract."""
    def _load(*_args, **_kwargs):
        fr = SimpleNamespace(
            pulse_id="p1",
            timestamp=1.0,
            triggers=[SimpleNamespace(kind="event", origin="angelia", item_type="manual", item_id="e1", content="x", title="", sender="")],
            agent_response=SimpleNamespace(text="hello", tool_calls=[]),
        )
        return [fr], ["p1: missing pulse.finish"]

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)
    with pytest.raises(ValueError, match="PULSE_INTEGRITY_ERROR"):
        janus_facade.SequentialV1Strategy().build(_req())


def test_build_succeeds_when_integrity_ok(monkeypatch):
    def _load(*_args, **_kwargs):
        fr = SimpleNamespace(
            pulse_id="p1",
            timestamp=1.0,
            triggers=[SimpleNamespace(kind="event", origin="angelia", item_type="manual", item_id="e1", content="manual", title="", sender="")],
            agent_response=SimpleNamespace(text="", tool_calls=[]),
        )
        return [fr], []

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)
    out = janus_facade.SequentialV1Strategy().build(_req())
    blob = "\n".join(out.system_blocks)
    assert '<pulse id="p1" state="processing">' in blob


def test_build_fails_when_trigger_empty(monkeypatch):
    """Triggerless pulse must fail under strict pulse contract."""
    def _load(*_args, **_kwargs):
        return [SimpleNamespace(pulse_id="p_bad", timestamp=1.0, triggers=[], agent_response=SimpleNamespace(text="", tool_calls=[]))], []

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)
    with pytest.raises(ValueError, match="PULSE_EMPTY_TRIGGER"):
        janus_facade.SequentialV1Strategy().build(_req())
