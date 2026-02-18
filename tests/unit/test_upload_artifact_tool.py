from __future__ import annotations

import json
import shutil
from pathlib import Path

from gods.tools.mnemosyne import upload_artifact
from gods.mnemosyne import facade as mnemosyne_facade


def test_upload_artifact_tool_creates_agent_scope_ref():
    project_id = "unit_upload_artifact_tool"
    caller_id = "sender"
    base = Path("projects") / project_id / "agents" / caller_id
    shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
    try:
        base.mkdir(parents=True, exist_ok=True)
        p = base / "doc.md"
        p.write_text("# hello", encoding="utf-8")
        out = upload_artifact.invoke(
            {
                "path": "doc.md",
                "scope": "agent",
                "mime": "text/markdown",
                "tags_json": '["x"]',
                "caller_id": caller_id,
                "project_id": project_id,
            }
        )
        row = json.loads(out)
        assert row.get("ok") is True
        aid = str(row.get("artifact_id", ""))
        assert aid.startswith("artf_")
        ref = mnemosyne_facade.head_artifact(aid, caller_id, project_id)
        assert ref.scope == "agent"
        assert ref.owner_agent_id == caller_id
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)

