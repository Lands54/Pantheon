from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from gods.mnemosyne import write_entry, list_entries, read_entry


def test_mnemosyne_write_list_read():
    project_id = f"mnemo_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        row = write_entry(project_id, "agent", "alpha", "test title", "hello archive", ["t1", "t2"])
        assert row["entry_id"]
        rows = list_entries(project_id, "agent", limit=10)
        assert any(x.get("entry_id") == row["entry_id"] for x in rows)
        full = read_entry(project_id, "agent", row["entry_id"])
        assert full is not None
        assert "hello archive" in full["content"]
    finally:
        if base.exists():
            shutil.rmtree(base)
