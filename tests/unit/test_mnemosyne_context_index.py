from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from gods.mnemosyne import MemoryIntent, record_intent
from gods.mnemosyne.facade import (
    list_context_index_entries,
    list_context_index_texts,
    rebuild_context_index_from_intents,
)


def test_record_intent_writes_intent_ledger_and_context_index():
    project_id = "unit_mn_context_index"
    agent_id = "alpha"
    root = Path("projects") / project_id
    shutil.rmtree(root, ignore_errors=True)
    try:
        intent = MemoryIntent(
            intent_key="tool.read.error",
            project_id=project_id,
            agent_id=agent_id,
            source_kind="tool",
            payload={
                "tool_name": "read",
                "status": "error",
                "args": {"path": "a.txt"},
                "result": "read failed",
                "result_compact": "read failed",
            },
            fallback_text="[TOOL] read error",
            timestamp=time.time(),
        )
        rec = record_intent(intent)
        assert rec.get("runtime_log_written") is True

        intents_path = root / "mnemosyne" / "intents" / f"{agent_id}.jsonl"
        assert intents_path.exists()
        lines = [x for x in intents_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert lines
        row = json.loads(lines[-1])
        assert row.get("intent_key") == "tool.read.error"
        assert row.get("source_kind") == "tool"
        assert int(row.get("intent_seq") or 0) >= 1
        assert str(row.get("intent_id") or "").startswith(f"{agent_id}:")

        idx_rows = list_context_index_entries(project_id, agent_id, limit=20)
        assert idx_rows
        assert idx_rows[-1].get("intent_key") == "tool.read.error"
        assert idx_rows[-1].get("source_intent_seq") == row.get("intent_seq")
        assert idx_rows[-1].get("source_intent_id") == row.get("intent_id")
        texts = list_context_index_texts(project_id, agent_id, limit=20)
        assert texts

        intent2 = MemoryIntent(
            intent_key="tool.read.error",
            project_id=project_id,
            agent_id=agent_id,
            source_kind="tool",
            payload={
                "tool_name": "read",
                "status": "error",
                "args": {"path": "b.txt"},
                "result": "read failed again",
                "result_compact": "read failed again",
            },
            fallback_text="[TOOL] read error again",
            timestamp=time.time(),
        )
        record_intent(intent2)
        lines2 = [x for x in intents_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        row2 = json.loads(lines2[-1])
        assert int(row2.get("intent_seq") or 0) == int(row.get("intent_seq") or 0) + 1

        idx_path = root / "mnemosyne" / "context_index" / f"{agent_id}.jsonl"
        idx_path.unlink(missing_ok=True)
        rebuilt = rebuild_context_index_from_intents(project_id, agent_id, limit=100)
        assert rebuilt.get("source_intents", 0) >= 2
        assert rebuilt.get("rows", 0) >= 1
        rows_after = list_context_index_entries(project_id, agent_id, limit=20)
        assert rows_after
        assert str(rows_after[-1].get("source_intent_id") or "").startswith(f"{agent_id}:")
        assert int(rows_after[-1].get("source_intent_seq") or 0) >= 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
