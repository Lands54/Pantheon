"""Event enqueue hook registry.

Used to attach cross-cutting reactions (e.g., wakeup) without coupling
`gods.events` store to specific domains.
"""
from __future__ import annotations

from typing import Callable

from gods.events.models import EventRecord

EnqueueHook = Callable[[EventRecord], None]

_HOOKS: list[EnqueueHook] = []


def register_enqueue_hook(hook: EnqueueHook) -> None:
    if hook in _HOOKS:
        return
    _HOOKS.append(hook)


def dispatch_enqueue_hooks(record: EventRecord) -> None:
    for hook in list(_HOOKS):
        try:
            hook(record)
        except Exception:
            continue
