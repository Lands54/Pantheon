from __future__ import annotations

from gods.janus.facade import StructuredV1ContextStrategy


def test_material_cards_are_not_merged_into_derived():
    strategy = StructuredV1ContextStrategy()
    cards = [
        {
            "card_id": "material.profile",
            "kind": "task",
            "priority": 100,
            "text": "x" * 400,
            "source_intent_ids": [],
            "source_intent_seq_max": 1,
            "derived_from_card_ids": [],
            "supersedes_card_ids": [],
            "compression_type": "",
            "meta": {},
            "created_at": 1.0,
        },
        {
            "card_id": "event:a",
            "kind": "event",
            "priority": 70,
            "text": "event a " * 60,
            "source_intent_ids": ["a:1"],
            "source_intent_seq_max": 1,
            "derived_from_card_ids": [],
            "supersedes_card_ids": [],
            "compression_type": "",
            "meta": {},
            "created_at": 1.0,
        },
        {
            "card_id": "event:b",
            "kind": "event",
            "priority": 70,
            "text": "event b " * 60,
            "source_intent_ids": ["a:2"],
            "source_intent_seq_max": 2,
            "derived_from_card_ids": [],
            "supersedes_card_ids": [],
            "compression_type": "",
            "meta": {},
            "created_at": 1.0,
        },
    ]
    out, dropped, meta = strategy.compress_cards_if_needed(cards, token_budget_total=60)
    assert meta.get("compressed") is True
    derived = [c for c in out if str(c.get("kind", "")) == "derived"]
    assert derived
    assert all(not str(c.get("card_id", "")).startswith("material.") for c in derived)
    assert all("material.profile" not in list(c.get("derived_from_card_ids", []) or []) for c in derived)
    assert all("material.profile" not in list(c.get("supersedes_card_ids", []) or []) for c in derived)
    assert dropped
