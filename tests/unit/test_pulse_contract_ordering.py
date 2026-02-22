from __future__ import annotations

from types import SimpleNamespace

from gods.janus.facade import ContextBuildRequest, SequentialV1Strategy


def _req() -> ContextBuildRequest:
    return ContextBuildRequest(
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


def test_trigger_text_tool_ordering_in_pulse(monkeypatch):
    def _load(*_args, **_kwargs):
        fr = SimpleNamespace(pulse_id="pulse_2", timestamp=1.0, triggers=[], agent_response=SimpleNamespace(text="", tool_calls=[]))
        fr.triggers = [SimpleNamespace(kind="event", origin="angelia", item_type="manual", item_id="ev2", title="", sender="", content="evt")]
        fr.agent_response.text = "resp"
        fr.agent_response.tool_calls = [SimpleNamespace(name="list", call_id="c1", status="ok", args={"path": "."}, result="ok")]
        return [fr], []

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)
    out = SequentialV1Strategy().build(_req())
    blob = "\n".join(out.system_blocks)
    i_trigger = blob.find("<trigger>")
    i_text = blob.find("<textresponse>")
    i_tool = blob.find("<tool_call ")
    assert i_trigger >= 0 and i_text >= 0 and i_tool >= 0
    assert i_trigger < i_text < i_tool


def test_pulse_start_is_not_considered_trigger(monkeypatch):
    def _load(*_args, **_kwargs):
        fr = SimpleNamespace(pulse_id="pulse_77", timestamp=1.0, triggers=[], agent_response=SimpleNamespace(text="", tool_calls=[]))
        fr.triggers = [SimpleNamespace(kind="event", origin="internal", item_type="pulse.start", item_id="pulse_77", title="", sender="", content="mail_event")]
        return [fr], []

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)
    try:
        SequentialV1Strategy().build(_req())
        assert False, "expected PULSE_EMPTY_TRIGGER because pulse.start is lifecycle marker, not trigger"
    except ValueError as e:
        assert "PULSE_EMPTY_TRIGGER" in str(e)
