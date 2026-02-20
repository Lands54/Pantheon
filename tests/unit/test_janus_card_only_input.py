from __future__ import annotations

import pytest

from gods.janus.facade import ContextBuildRequest, StructuredV1ContextStrategy


def _base_card(card_id: str, kind: str, text: str) -> dict:
    return {
        "card_id": card_id,
        "kind": kind,
        "priority": 80,
        "text": text,
        "source_intent_ids": [],
        "source_intent_seq_max": 1,
        "derived_from_card_ids": [],
        "supersedes_card_ids": [],
        "compression_type": "",
        "meta": {},
        "created_at": 1.0,
    }


def test_janus_card_only_input_builds():
    req = ContextBuildRequest(
        project_id="unit_janus_card_only_input",
        agent_id="alpha",
        state={},
        directives="d",
        local_memory="",
        inbox_hint="",
        phase_name="react_graph",
        tools_desc="- t",
        context_cfg={"token_budget_total": 4000},
        context_materials={
            "intent_seq_latest": 1,
            "card_buckets": {
                "profile": [_base_card("material.profile", "task", "[PROFILE]\\na")],
                "task_state": [_base_card("material.task_state", "task", "[TASK]\\nobj")],
                "mailbox": [_base_card("material.mailbox", "mailbox", "[MAILBOX]\\nnone")],
                "events": [_base_card("material.trigger", "event", "[TRIGGER]\\nnone")],

                "policy": [_base_card("material.phase", "policy", "[PHASE]\\nreact_graph")],
            },
        },
    )
    res = StructuredV1ContextStrategy().build(req)
    assert res.strategy_used == "structured_v1"
    assert "# CARD_CONTEXT" in "\n\n".join(res.system_blocks)


def test_janus_card_only_input_rejects_legacy_materials_without_buckets():
    req = ContextBuildRequest(
        project_id="unit_janus_card_only_input",
        agent_id="alpha",
        state={},
        directives="d",
        local_memory="",
        inbox_hint="",
        phase_name="react_graph",
        tools_desc="- t",
        context_cfg={"token_budget_total": 4000},
        context_materials={
            "intent_seq_latest": 1,
            "profile": "# old profile",
            "chronicle_index_rendered": ["legacy"],
        },
    )
    with pytest.raises(ValueError, match="JANUS_CARD_BUCKETS_REQUIRED"):
        StructuredV1ContextStrategy().build(req)


def test_janus_filters_long_cards_before_snapshot_base_seq(monkeypatch):
    strategy = StructuredV1ContextStrategy()

    monkeypatch.setattr(
        "gods.janus.strategies.structured_v1.load_janus_snapshot",
        lambda _p, _a: {"base_intent_seq": 50},
    )
    monkeypatch.setattr(
        "gods.janus.strategies.structured_v1.build_cards_from_intent_views",
        lambda *_args, **_kwargs: [
            {
                "card_id": "intent.long:old",
                "kind": "chronicle_summary",
                "priority": 70,
                "text": "old long",
                "source_intent_ids": ["alpha:10"],
                "source_intent_seq_max": 10,
                "derived_from_card_ids": [],
                "supersedes_card_ids": [],
                "compression_type": "",
                "meta": {"memory_span": "long"},
                "created_at": 1.0,
            },
            {
                "card_id": "intent.short:new",
                "kind": "event",
                "priority": 80,
                "text": "new short",
                "source_intent_ids": ["alpha:120"],
                "source_intent_seq_max": 120,
                "derived_from_card_ids": [],
                "supersedes_card_ids": [],
                "compression_type": "",
                "meta": {"memory_span": "short"},
                "created_at": 2.0,
            },
        ],
    )

    cards, meta = strategy._resolve_cards_from_chaos(
        ContextBuildRequest(
            project_id="unit_janus_card_only_input",
            agent_id="alpha",
            state={},
            directives="d",
            local_memory="",
            inbox_hint="",
            phase_name="react_graph",
            tools_desc="- t",
            context_cfg={"token_budget_total": 4000},
            context_materials={
                "intent_seq_latest": 120,
                "card_buckets": {
                    "profile": [_base_card("material.profile", "task", "[PROFILE]\\na")],
                    "task_state": [_base_card("material.task_state", "task", "[TASK]\\nobj")],
                    "mailbox": [_base_card("material.mailbox", "mailbox", "[MAILBOX]\\nnone")],
                    "events": [_base_card("material.trigger", "event", "[TRIGGER]\\nnone")],

                    "policy": [_base_card("material.phase", "policy", "[PHASE]\\nreact_graph")],
                },
            },
        ),
        {"intent_seq_latest": 120, "card_buckets": {
            "profile": [_base_card("material.profile", "task", "[PROFILE]\\na")],
            "task_state": [_base_card("material.task_state", "task", "[TASK]\\nobj")],
            "mailbox": [_base_card("material.mailbox", "mailbox", "[MAILBOX]\\nnone")],
            "events": [_base_card("material.trigger", "event", "[TRIGGER]\\nnone")],

            "policy": [_base_card("material.phase", "policy", "[PHASE]\\nreact_graph")],
        }},
    )
    card_ids = {str(c.get("card_id", "")) for c in cards}
    assert "intent.long:old" not in card_ids
    assert "intent.short:new" in card_ids
    assert int(meta.get("base_intent_seq", 0)) >= 50
