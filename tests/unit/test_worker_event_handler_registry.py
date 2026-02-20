from __future__ import annotations

from types import SimpleNamespace

from gods import events as events_bus
from gods.angelia import worker


def test_worker_resolve_handler_registers_default():
    events_bus.clear_handlers()
    h = worker._resolve_handler("manual")
    assert h is not None
    assert events_bus.get_handler("manual") is h


def test_worker_resolve_handler_returns_none_for_non_llm_event():
    events_bus.clear_handlers()
    h = worker._resolve_handler("interaction.message.read")
    assert h is None


def test_worker_resolve_handler_rejects_unknown_event():
    events_bus.clear_handlers()
    try:
        worker._resolve_handler("unknown.random.event")
        assert False, "expected unknown event to be rejected"
    except ValueError as e:
        assert "EVENT_CATALOG_MISSING" in str(e)


def test_worker_record_event_lifecycle_intent_calls_record_intent(monkeypatch):
    captured = {}

    def _fake_builder(event, stage, extra_payload=None):
        return {"event_id": getattr(event, "event_id", ""), "stage": stage, "extra": dict(extra_payload or {})}

    def _fake_record(intent):
        captured["intent"] = intent

    monkeypatch.setattr(worker, "intent_from_angelia_event", _fake_builder)
    monkeypatch.setattr(worker, "record_intent", _fake_record)
    evt = SimpleNamespace(project_id="p", agent_id="a", event_id="e1")
    worker._record_event_lifecycle_intent(evt, "done", {"next_step": "finish"})
    assert captured.get("intent", {}).get("event_id") == "e1"
    assert captured.get("intent", {}).get("stage") == "done"
    assert captured.get("intent", {}).get("extra", {}).get("next_step") == "finish"
