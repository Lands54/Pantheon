from __future__ import annotations

from gods import events as events_bus
from gods.angelia import worker


def test_worker_resolve_handler_registers_default():
    events_bus.clear_handlers()
    h = worker._resolve_handler("manual_event")
    assert h is not None
    assert events_bus.get_handler("manual_event") is h

