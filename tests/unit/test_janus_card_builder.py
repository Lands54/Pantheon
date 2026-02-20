from __future__ import annotations

import shutil
import time
from pathlib import Path

from gods.mnemosyne import MemoryIntent, record_intent
from gods.mnemosyne.facade import build_cards_from_intents, build_cards_from_intent_views


def test_build_cards_from_intents_tracks_sources():
    project_id = "unit_janus_card_builder"
    agent_id = "alpha"
    root = Path("projects") / project_id
    shutil.rmtree(root, ignore_errors=True)
    try:
        record_intent(
            MemoryIntent(
                intent_key="tool.read.error",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="tool",
                payload={"tool_name": "read", "status": "error", "args": {"path": "a.txt"}, "result": "e", "result_compact": "e"},
                fallback_text="tool read error",
                timestamp=time.time(),
            )
        )
        record_intent(
            MemoryIntent(
                intent_key="inbox.section.summary",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="inbox",
                payload={"section": "summary", "title": "SUMMARY", "rows": "- unread=1"},
                fallback_text="[SUMMARY]\\n- unread=1",
                timestamp=time.time(),
            )
        )

        cards = build_cards_from_intents(project_id, agent_id, from_intent_seq=0, limit=50)
        assert cards
        assert all(str(c.get("card_id", "")).strip() for c in cards)
        assert all(int(c.get("source_intent_seq_max", 0) or 0) >= 1 for c in cards)
        assert all(list(c.get("source_intent_ids", []) or []) for c in cards)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_cards_from_intent_views_respects_long_short_split():
    project_id = "unit_janus_card_views_split"
    agent_id = "alpha"
    root = Path("projects") / project_id
    shutil.rmtree(root, ignore_errors=True)
    try:
        r1 = record_intent(
            MemoryIntent(
                intent_key="llm.response",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="llm",
                payload={"phase": "react_graph", "content": "first response"},
                fallback_text="first response",
                timestamp=time.time(),
            )
        )
        r2 = record_intent(
            MemoryIntent(
                intent_key="inbox.section.summary",
                project_id=project_id,
                agent_id=agent_id,
                source_kind="inbox",
                payload={"section": "summary", "title": "SUMMARY", "rows": "- unread=1"},
                fallback_text="[SUMMARY]\\n- unread=1",
                timestamp=time.time(),
            )
        )
        split = int(r1.get("intent_seq", 0) or 0)
        latest = int(r2.get("intent_seq", 0) or 0)
        cards = build_cards_from_intent_views(
            project_id,
            agent_id,
            split_intent_seq=split,
            to_intent_seq=latest,
        )
        assert cards
        long_cards = [c for c in cards if str((c.get("meta", {}) or {}).get("memory_span", "")) == "long"]
        short_cards = [c for c in cards if str((c.get("meta", {}) or {}).get("memory_span", "")) == "short"]
        assert long_cards, "expected long cards for seq <= split"
        assert short_cards, "expected short cards for seq > split"
        assert all(int(c.get("source_intent_seq_max", 0) or 0) <= split for c in long_cards)
        assert all(int(c.get("source_intent_seq_max", 0) or 0) > split for c in short_cards)
    finally:
        shutil.rmtree(root, ignore_errors=True)
