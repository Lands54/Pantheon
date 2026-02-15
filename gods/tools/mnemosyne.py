"""Mnemosyne tools for agents (agent-vault only)."""
from __future__ import annotations

import json

from langchain.tools import tool

from gods.mnemosyne import write_entry, list_entries, read_entry


@tool
def mnemo_write_agent(title: str, content: str, tags_json: str = "[]", caller_id: str = "default", project_id: str = "default") -> str:
    """Write durable archive entry to Mnemosyne agent vault (agent-readable)."""
    try:
        tags = json.loads(tags_json) if tags_json.strip() else []
        row = write_entry(project_id, "agent", caller_id, title, content, tags if isinstance(tags, list) else [])
        return json.dumps({"ok": True, "entry": row}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def mnemo_list_agent(limit: int = 20, caller_id: str = "default", project_id: str = "default") -> str:
    """List Mnemosyne agent-vault entries in current project."""
    try:
        rows = list_entries(project_id, "agent", limit=int(limit))
        return json.dumps({"ok": True, "entries": rows}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def mnemo_read_agent(entry_id: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Read one Mnemosyne agent-vault entry by id."""
    try:
        row = read_entry(project_id, "agent", entry_id)
        if not row:
            return json.dumps({"ok": False, "error": "entry not found"}, ensure_ascii=False)
        return json.dumps({"ok": True, **row}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
