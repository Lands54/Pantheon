"""Hermes error codes and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HERMES_PROTOCOL_NOT_FOUND = "HERMES_PROTOCOL_NOT_FOUND"
HERMES_SCHEMA_INVALID = "HERMES_SCHEMA_INVALID"
HERMES_RATE_LIMITED = "HERMES_RATE_LIMITED"
HERMES_BUSY = "HERMES_BUSY"
HERMES_TIMEOUT = "HERMES_TIMEOUT"
HERMES_PROVIDER_ERROR = "HERMES_PROVIDER_ERROR"
HERMES_BAD_REQUEST = "HERMES_BAD_REQUEST"


@dataclass
class HermesError(Exception):
    code: str
    message: str
    retryable: bool = False
    details: Any = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }
