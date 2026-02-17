"""Event handler contract."""
from __future__ import annotations

from abc import ABC
from typing import Any

from gods.events.models import EventRecord


class EventHandler(ABC):
    event_type: str = ""

    def on_pick(self, record: EventRecord) -> None:
        _ = record

    def on_process(self, record: EventRecord) -> dict[str, Any]:
        _ = record
        return {}

    def on_success(self, record: EventRecord, result: dict[str, Any]) -> None:
        _ = (record, result)

    def on_fail(self, record: EventRecord, err: Exception) -> None:
        _ = (record, err)

    def on_dead(self, record: EventRecord, err: Exception) -> None:
        _ = (record, err)
