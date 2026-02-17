"""Interaction domain errors."""
from __future__ import annotations


class InteractionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = str(code or "INTERACTION_ERROR")
        self.message = str(message or "interaction error")

