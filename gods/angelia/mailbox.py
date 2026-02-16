"""Per-agent in-memory mailbox notifications."""
from __future__ import annotations

import threading


class _MailboxSlot:
    def __init__(self):
        self.cv = threading.Condition()
        self.pending = 0


class AngeliaMailbox:
    def __init__(self):
        self._guard = threading.Lock()
        self._slots: dict[tuple[str, str], _MailboxSlot] = {}

    def _slot(self, project_id: str, agent_id: str) -> _MailboxSlot:
        key = (project_id, agent_id)
        with self._guard:
            slot = self._slots.get(key)
            if slot is None:
                slot = _MailboxSlot()
                self._slots[key] = slot
            return slot

    def notify(self, project_id: str, agent_id: str):
        slot = self._slot(project_id, agent_id)
        with slot.cv:
            slot.pending += 1
            slot.cv.notify()

    def wait(self, project_id: str, agent_id: str, timeout: float = 1.0) -> bool:
        slot = self._slot(project_id, agent_id)
        with slot.cv:
            if slot.pending <= 0:
                slot.cv.wait(timeout=max(0.05, float(timeout)))
            if slot.pending > 0:
                slot.pending -= 1
                return True
            return False


angelia_mailbox = AngeliaMailbox()
