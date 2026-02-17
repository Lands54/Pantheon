"""Event handler registry."""
from __future__ import annotations

from gods.events.handler import EventHandler


_REGISTRY: dict[str, EventHandler] = {}


def register_handler(event_type: str, handler: EventHandler):
    _REGISTRY[str(event_type)] = handler


def get_handler(event_type: str) -> EventHandler | None:
    return _REGISTRY.get(str(event_type))


def clear_handlers():
    _REGISTRY.clear()


def all_handlers() -> dict[str, EventHandler]:
    return dict(_REGISTRY)
