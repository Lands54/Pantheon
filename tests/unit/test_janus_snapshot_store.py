from __future__ import annotations

import json
import shutil
from pathlib import Path

from gods.mnemosyne.facade import (
    list_derived_cards,
    list_snapshot_compressions,
    load_janus_snapshot,
    record_snapshot_compression,
    save_janus_snapshot,
)


def test_janus_snapshot_latest_only_store_and_corruption_fallback():
    project_id = "unit_janus_snapshot_store"
    agent_id = "alpha"
    root = Path("projects") / project_id
    shutil.rmtree(root, ignore_errors=True)
    try:
        snap = {
            "snapshot_id": "snap_a_1",
            "project_id": project_id,
            "agent_id": agent_id,
            "base_intent_seq": 12,
            "token_estimate": 30,
            "cards": [{"card_id": "event:mail_event", "kind": "event", "priority": 70, "text": "mail", "source_intent_ids": ["alpha:12"], "source_intent_seq_max": 12, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
            "dropped": [],
            "created_at": 1.0,
            "updated_at": 1.0,
        }
        save_janus_snapshot(project_id, agent_id, snap)
        loaded = load_janus_snapshot(project_id, agent_id)
        assert loaded is not None
        assert loaded.get("base_intent_seq") == 12
        assert len(list(loaded.get("cards", []) or [])) == 1

        save_janus_snapshot(project_id, agent_id, {**snap, "snapshot_id": "snap_a_2", "base_intent_seq": 25})
        loaded2 = load_janus_snapshot(project_id, agent_id)
        assert loaded2 is not None
        assert loaded2.get("snapshot_id") == "snap_a_2"
        assert loaded2.get("base_intent_seq") == 25

        p = root / "mnemosyne" / "janus_snapshot" / f"{agent_id}.json"
        p.write_text("{", encoding="utf-8")
        assert load_janus_snapshot(project_id, agent_id) is None

        record_snapshot_compression(
            project_id,
            agent_id,
            {
                "snapshot_id": "snap_a_2",
                "derived_count": 1,
                "before_tokens": 200,
                "after_tokens": 120,
                "derived": [
                    {
                        "card_id": "derived:event:1",
                        "derived_from_card_ids": ["event:a", "event:b"],
                        "supersedes_card_ids": ["event:a", "event:b"],
                        "source_intent_ids": ["alpha:21", "alpha:22"],
                    }
                ],
            },
        )
        logs = list_snapshot_compressions(project_id, agent_id, limit=10)
        assert logs
        assert logs[-1].get("snapshot_id") == "snap_a_2"
        assert int(logs[-1].get("derived_count", 0) or 0) == 1
        derived_rows = list_derived_cards(project_id, agent_id, limit=10)
        assert derived_rows
        d0 = derived_rows[-1].get("derived_card", {}) or {}
        assert d0.get("card_id") == "derived:event:1"
        assert d0.get("derived_from_card_ids") == ["event:a", "event:b"]
        assert d0.get("supersedes_card_ids") == ["event:a", "event:b"]
        assert d0.get("source_intent_ids") == ["alpha:21", "alpha:22"]
    finally:
        shutil.rmtree(root, ignore_errors=True)
