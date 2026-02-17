"""Outbox receipt models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OutboxReceiptStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    HANDLED = "handled"
    FAILED = "failed"


@dataclass
class OutboxReceipt:
    receipt_id: str
    project_id: str
    from_agent_id: str
    to_agent_id: str
    title: str
    message_id: str
    status: OutboxReceiptStatus
    created_at: float
    updated_at: float
    error_message: str = ""

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "project_id": self.project_id,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "title": self.title,
            "message_id": self.message_id,
            "status": self.status.value,
            "created_at": float(self.created_at),
            "updated_at": float(self.updated_at),
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, row: dict) -> "OutboxReceipt":
        return cls(
            receipt_id=str(row.get("receipt_id", "")),
            project_id=str(row.get("project_id", "")),
            from_agent_id=str(row.get("from_agent_id", "")),
            to_agent_id=str(row.get("to_agent_id", "")),
            title=str(row.get("title", "(untitled)") or "(untitled)"),
            message_id=str(row.get("message_id", "")),
            status=OutboxReceiptStatus(str(row.get("status", OutboxReceiptStatus.PENDING.value))),
            created_at=float(row.get("created_at", 0.0) or 0.0),
            updated_at=float(row.get("updated_at", row.get("created_at", 0.0)) or 0.0),
            error_message=str(row.get("error_message", "")),
        )

