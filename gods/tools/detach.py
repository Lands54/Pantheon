"""Detach tool wrappers for agents."""
from __future__ import annotations

import json

from langchain.tools import tool

from gods.runtime.detach import DetachError, list_for_api, stop, submit


def _err(e: Exception) -> str:
    if isinstance(e, DetachError):
        return f"Detach Error [{e.code}]: {e.message}"
    return f"Detach Error [DETACH_UNKNOWN]: {e}"


@tool
def run_command_detach(command: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Submit a validated background command job (detach) for current agent in docker runtime."""
    try:
        res = submit(project_id=project_id, agent_id=caller_id, command=command)
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@tool
def detach_list(caller_id: str = "default", project_id: str = "default", status: str = "", limit: int = 20) -> str:
    """List detach jobs in current project (optionally filter by status)."""
    try:
        res = list_for_api(project_id=project_id, agent_id="", status=status, limit=limit)
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return _err(e)


@tool
def detach_stop(job_id: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Stop a running detach job by id."""
    try:
        res = stop(project_id=project_id, job_id=job_id, reason="manual")
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return _err(e)
