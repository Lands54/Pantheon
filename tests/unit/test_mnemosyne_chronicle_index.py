from __future__ import annotations

import shutil
import time
from pathlib import Path

from gods.mnemosyne import MemoryIntent, record_intent
from gods.mnemosyne.facade import (
    list_chronicle_index_entries,
    list_chronicle_index_texts,
    rebuild_chronicle_markdown_from_index,
)


def test_record_intent_writes_chronicle_index_and_rebuild_markdown():
    project_id = "unit_mn_chronicle_index"
    agent_id = "alpha"
    root = Path("projects") / project_id
    shutil.rmtree(root, ignore_errors=True)
    try:
        intent = MemoryIntent(
            intent_key="llm.response",
            project_id=project_id,
            agent_id=agent_id,
            source_kind="llm",
            payload={"phase": "think", "content": "hello world"},
            fallback_text="hello world",
            timestamp=time.time(),
        )
        rec = record_intent(intent)
        assert rec.get("chronicle_written") is True

        rows = list_chronicle_index_entries(project_id, agent_id, limit=20)
        assert rows
        assert rows[-1].get("intent_key") == "llm.response"
        assert int(rows[-1].get("source_intent_seq") or 0) >= 1
        assert str(rows[-1].get("source_intent_id") or "").startswith(f"{agent_id}:")
        texts = list_chronicle_index_texts(project_id, agent_id, limit=20)
        assert texts

        rebuilt = rebuild_chronicle_markdown_from_index(project_id, agent_id)
        assert rebuilt.get("rows", 0) >= 1
        md = root / "mnemosyne" / "chronicles" / f"{agent_id}.md"
        assert md.exists()
        txt = md.read_text(encoding="utf-8")
        assert "llm.response" in txt
        assert f"{agent_id}:" in txt
    finally:
        shutil.rmtree(root, ignore_errors=True)
