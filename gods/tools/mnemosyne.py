"""Mnemosyne tools for agents (agent-vault only)."""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from langchain_core.tools import tool

from gods.mnemosyne import write_entry, list_entries, read_entry
from gods.mnemosyne import facade as mnemosyne_facade
from gods.tools.filesystem import validate_path


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


@tool
def upload_artifact(
    path: str,
    scope: str = "agent",
    mime: str = "",
    tags_json: str = "[]",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Upload one local file as Mnemosyne artifact and return artifact_id (default private agent scope)."""
    try:
        p = validate_path(caller_id, project_id, path)
        if not p.exists() or not p.is_file():
            return json.dumps({"ok": False, "error": f"file not found: {path}"}, ensure_ascii=False)
        data = p.read_bytes()
        mime_val = str(mime or "").strip() or str(mimetypes.guess_type(str(p))[0] or "application/octet-stream")
        tags = json.loads(tags_json) if str(tags_json or "").strip() else []
        if not isinstance(tags, list):
            return json.dumps({"ok": False, "error": "tags_json must be JSON array"}, ensure_ascii=False)
        sc = str(scope or "agent").strip().lower()
        owner = caller_id if sc == "agent" else ""
        ref = mnemosyne_facade.put_artifact_bytes(
            scope=sc,
            project_id=project_id,
            owner_agent_id=owner,
            actor_id=caller_id,
            data=data,
            mime=mime_val,
            tags=[str(x).strip() for x in tags if str(x).strip()],
        )
        return json.dumps(
            {
                "ok": True,
                "artifact_id": ref.artifact_id,
                "scope": ref.scope,
                "mime": ref.mime,
                "size": ref.size,
                "sha256": ref.sha256,
                "source_path": str(Path(path)),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
