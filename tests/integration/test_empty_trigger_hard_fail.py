from __future__ import annotations

import pytest
from types import SimpleNamespace

from gods.janus import facade as janus_facade


def test_empty_trigger_hard_fail(monkeypatch):
    """Triggerless pulse must fail under strict pulse contract."""
    def _load(*_args, **_kwargs):
        return [SimpleNamespace(pulse_id="p_bad", timestamp=1.0, triggers=[], agent_response=SimpleNamespace(text="", tool_calls=[]))], []

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.load_pulse_frames", _load)
    req = janus_facade.ContextBuildRequest(
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
        janus_facade.SequentialV1Strategy().build(req)
