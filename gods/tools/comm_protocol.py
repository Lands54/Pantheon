"""Protocol recording communication tool."""
from __future__ import annotations

from langchain.tools import tool

from gods.tools.comm_common import format_comm_error


@tool
def record_protocol(
    topic: str,
    relation: str,
    object: str,
    clause: str,
    counterparty: str = "",
    status: str = "agreed",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Deprecated compatibility path. Use register_contract as external minimum unit."""
    _ = (topic, relation, object, clause, counterparty, status)  # keep signature stable
    return format_comm_error(
        "Protocol Deprecated",
        "record_protocol is deprecated and no longer registers executable protocols.",
        "Use register_contract/commit_contract/list_contracts (contract-first flow).",
        caller_id,
        project_id,
    )
