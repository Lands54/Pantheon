from __future__ import annotations

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
