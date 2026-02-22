from __future__ import annotations

from types import SimpleNamespace
from xml.etree import ElementTree as ET

from gods.janus.facade import ContextBuildRequest, SequentialV1Strategy


def test_sequential_v1_emits_tagged_static_and_pulse_blocks(monkeypatch):
    def _load(*_args, **_kwargs):
        fr = SimpleNamespace(pulse_id="pulse_1", timestamp=1.0, triggers=[], agent_response=SimpleNamespace(text="", tool_calls=[]))
        fr.triggers = [SimpleNamespace(kind="event", origin="angelia", item_type="manual", item_id="ev1", title="", sender="", content="one")]
        fr.agent_response.text = "reply 1"
        return [fr], []

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)
    req = ContextBuildRequest(
        project_id="p",
        agent_id="a",
        state={},
        directives="be precise",
        local_memory="",
        inbox_hint="check inbox once per pulse",
        tools_desc="- [[list(path)]]",
        context_cfg={},
        context_materials=SimpleNamespace(
            profile="alpha profile",
            directives="",
            task_state="objective: x",
            tools="",
            inbox_hint="",
        ),
    )
    out = SequentialV1Strategy().build(req)
    blob = "\n".join(out.system_blocks)
    assert blob.startswith("<?xml version='1.0' encoding='utf-8'?>")
    ET.fromstring(blob)
    assert "<profile>" in blob
    assert "<directives>be precise</directives>" in blob
    assert "<task_state>objective: x</task_state>" in blob
    assert "<tools>- [[list(path)]]</tools>" in blob
    assert "<inbox_hint>check inbox once per pulse</inbox_hint>" in blob
    assert '<pulse id="pulse_1" state="processing">' in blob
