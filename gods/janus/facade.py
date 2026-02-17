"""Public facade for janus domain operations."""
from __future__ import annotations

from gods.janus import janus_service, record_inbox_digest, record_observation
from gods.janus.context_policy import resolve_context_cfg
from gods.janus.journal import (
    inbox_digest_path,
    latest_context_report,
    list_observations,
    observations_path,
)
from gods.janus.models import ContextBuildRequest, ObservationRecord
from gods.janus.strategies.structured_v1 import StructuredV1ContextStrategy


def context_preview(project_id: str, agent_id: str):
    return janus_service.context_preview(project_id, agent_id)


def context_reports(project_id: str, agent_id: str, limit: int = 20):
    return janus_service.context_reports(project_id, agent_id, limit=limit)


__all__ = [
    "context_preview",
    "context_reports",
    "record_observation",
    "record_inbox_digest",
    "resolve_context_cfg",
    "latest_context_report",
    "list_observations",
    "observations_path",
    "inbox_digest_path",
    "ObservationRecord",
    "ContextBuildRequest",
    "StructuredV1ContextStrategy",
]
