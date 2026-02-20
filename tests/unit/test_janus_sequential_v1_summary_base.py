from __future__ import annotations

from types import SimpleNamespace

from gods.janus.models import ContextBuildRequest
from gods.janus.strategies.sequential_v1 import SequentialV1Strategy


def _card(card_id: str, text: str, seq: int, intent_key: str = "event.manual") -> dict:
    return {
        "card_id": card_id,
        "kind": "event",
        "text": text,
        "source_intent_ids": [f"alpha:{seq}"] if seq > 0 else [],
        "source_intent_seq_max": seq,
        "derived_from_card_ids": [],
        "supersedes_card_ids": [],
        "compression_type": "",
        "meta": {"intent_key": intent_key},
        "created_at": float(max(1, seq)),
    }


def test_sequential_v1_uses_latest_summary_and_base_slice():
    strategy = SequentialV1Strategy()
    req = ContextBuildRequest(
        project_id="unit_seq_summary",
        agent_id="alpha",
        state={},
        directives="",
        local_memory="",
        inbox_hint="",
        tools_desc="",
        context_cfg={"n_recent": 1, "token_budget_chronicle_trigger": 999999},
        context_materials=SimpleNamespace(
            cards=[
                _card("material.profile", "[PROFILE]", -1, intent_key="material.profile"),
                _card("intent:1", "old-1", 1),
                _card("intent:2", "old-2", 2),
                _card(
                    "summary:3",
                    "[JANUS_COMPACTION_BASE]\nbase_intent_seq=2\nsum-old",
                    3,
                    intent_key="janus.compaction.base",
                ),
                _card("intent:4", "mid-4", 4),
                _card("intent:5", "recent-5", 5),
            ]
        ),
    )
    out = strategy.build(req)
    blob = "\n".join(out.system_blocks)
    assert "sum-old" in blob
    assert "mid-4" in blob
    assert "recent-5" in blob
    assert "old-1" not in blob
    assert "old-2" not in blob


def test_compress_chronicle_builds_base_summary_card(monkeypatch):
    strategy = SequentialV1Strategy()

    class _Brain:
        def think(self, prompt: str, trace_meta=None):
            return "compressed-summary"

    req = ContextBuildRequest(
        project_id="unit_seq_summary",
        agent_id="alpha",
        state={},
        directives="",
        local_memory="",
        inbox_hint="",
        tools_desc="",
        context_cfg={},
        agent=SimpleNamespace(brain=_Brain()),
        context_materials=SimpleNamespace(cards=[]),
    )

    monkeypatch.setattr(
        "gods.janus.strategies.sequential_v1.record_janus_compaction_base_intent",
        lambda *_args, **_kwargs: {"intent_id": "alpha:99", "intent_seq": 99},
    )
    cards = [
        _card("intent:10", "event-10", 10),
        _card("intent:11", "event-11", 11),
    ]
    row = strategy._compress_chronicle(req, cards)
    assert isinstance(row, dict)
    assert "base_intent_seq=11" in str(row.get("text", ""))
    assert int(row.get("source_intent_seq_max", 0) or 0) == 99
    assert str((row.get("meta", {}) or {}).get("intent_key", "")) == "janus.compaction.base"
    assert list(row.get("derived_from_card_ids", []) or []) == ["intent:10", "intent:11"]


def test_tools_desc_not_duplicated_when_material_tools_exists():
    strategy = SequentialV1Strategy()
    req = ContextBuildRequest(
        project_id="unit_seq_summary",
        agent_id="alpha",
        state={},
        directives="",
        local_memory="",
        inbox_hint="",
        tools_desc="[[send_message(...)]]",
        context_cfg={"n_recent": 2, "token_budget_chronicle_trigger": 999999},
        context_materials=SimpleNamespace(
            cards=[
                _card("material.profile", "[PROFILE]", -1, intent_key="material.profile"),
                _card("material.tools", "[TOOLS]\n[[send_message(...)]]", -1, intent_key="material.tools"),
                _card("intent:1", "recent-1", 1),
            ]
        ),
    )
    out = strategy.build(req)
    blob = "\n".join(out.system_blocks)
    assert blob.count("[[send_message(...)]]") == 1
    assert "## AVAILABLE TOOLS" not in blob
