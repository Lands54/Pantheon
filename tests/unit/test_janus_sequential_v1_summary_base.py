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


def test_compression_records_are_written_when_triggered(monkeypatch):
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
        context_cfg={"n_recent": 1, "token_budget_chronicle_trigger": 1},
        agent=SimpleNamespace(brain=_Brain()),
        context_materials=SimpleNamespace(
            cards=[
                _card("intent:10", "event-10 " * 50, 10),
                _card("intent:11", "event-11 " * 50, 11),
                _card("intent:12", "recent-12", 12),
            ]
        ),
    )

    called = {"n": 0, "row": None}

    monkeypatch.setattr(
        "gods.janus.strategies.sequential_v1.record_janus_compaction_base_intent",
        lambda *_args, **_kwargs: {"intent_id": "alpha:99", "intent_seq": 99},
    )
    monkeypatch.setattr(
        "gods.janus.strategies.sequential_v1.save_janus_snapshot",
        lambda *_args, **_kwargs: {"ok": True},
    )

    def _record(*_args, **_kwargs):
        called["n"] += 1
        called["row"] = _args[2] if len(_args) >= 3 else None
        return {"ok": True}

    monkeypatch.setattr("gods.janus.strategies.sequential_v1.record_snapshot_compression", _record)

    out = strategy.build(req)
    assert out.preview.get("compression", {}).get("triggered") is True
    assert called["n"] == 1
    assert isinstance(called["row"], dict)
    assert int(called["row"].get("derived_count", 0) or 0) == 1


def test_recent_window_can_be_token_budget_driven():
    strategy = SequentialV1Strategy()
    cards = [
        _card("intent:1", "a" * 40, 1),   # ~10 tok
        _card("intent:2", "b" * 40, 2),   # ~10 tok
        _card("intent:3", "c" * 40, 3),   # ~10 tok
    ]
    # budget=15 should keep only the latest card by token, regardless of n_recent fallback.
    chronicle, recents = strategy._split_recent_by_token_budget(
        cards,
        recent_count_fallback=3,
        recent_token_budget=15,
    )
    assert [c["card_id"] for c in recents] == ["intent:3"]
    assert [c["card_id"] for c in chronicle] == ["intent:1", "intent:2"]
