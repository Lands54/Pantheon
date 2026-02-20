from __future__ import annotations

from gods.janus.facade import StructuredV1ContextStrategy


def test_compress_cards_generates_derived_with_lineage():
    strategy = StructuredV1ContextStrategy()
    cards = [
        {
            "card_id": "event:contract.build",
            "kind": "event",
            "priority": 70,
            "text": "协议构建" * 30,
            "source_intent_ids": ["a:1"],
            "source_intent_seq_max": 1,
            "derived_from_card_ids": [],
            "supersedes_card_ids": [],
            "compression_type": "",
            "meta": {},
            "created_at": 1.0,
        },
        {
            "card_id": "event:contract.done",
            "kind": "event",
            "priority": 70,
            "text": "协议完成" * 30,
            "source_intent_ids": ["a:2"],
            "source_intent_seq_max": 2,
            "derived_from_card_ids": [],
            "supersedes_card_ids": [],
            "compression_type": "",
            "meta": {},
            "created_at": 2.0,
        },
    ]
    new_cards, dropped, meta = strategy.compress_cards_if_needed(cards, token_budget_total=20)
    assert meta.get("compressed") is True
    assert dropped
    derived = [c for c in new_cards if str(c.get("kind", "")) == "derived"]
    assert derived
    d0 = derived[0]
    assert list(d0.get("derived_from_card_ids", []) or [])
    assert list(d0.get("supersedes_card_ids", []) or [])
    assert sorted(list(d0.get("source_intent_ids", []) or [])) == ["a:1", "a:2"]
