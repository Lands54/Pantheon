"""Unified event-bus errors."""
from __future__ import annotations


class EventBusError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
