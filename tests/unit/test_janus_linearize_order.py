from __future__ import annotations

from gods.janus.facade import ContextBuildRequest, StructuredV1ContextStrategy


def _card(card_id: str, kind: str, priority: int, seq: int, text: str) -> dict:
    return {
        "card_id": card_id,
        "kind": kind,
        "priority": priority,
        "text": text,
        "source_intent_ids": [],
        "source_intent_seq_max": seq,
        "derived_from_card_ids": [],
        "supersedes_card_ids": [],
        "compression_type": "",
        "meta": {},
        "created_at": float(seq),
    }


def test_linearize_order_priority_then_seq():
    req = ContextBuildRequest(
        project_id="unit_janus_linearize_order",
        agent_id="alpha",
        state={},
        directives="d",
        local_memory="",
        inbox_hint="",
        phase_name="react_graph",
        tools_desc="- t",
        context_cfg={"token_budget_total": 8000},
        context_materials={
            "intent_seq_latest": 10,
            "card_buckets": {
                "profile": [_card("material.profile", "task", 100, 1, "P")],
                "task_state": [_card("material.task_state", "task", 98, 1, "T")],
                "mailbox": [_card("material.mailbox", "mailbox", 90, 1, "M")],
                "events": [_card("material.trigger", "event", 92, 1, "E")],

                "policy": [
                    _card("material.policy.a", "policy", 97, 2, "A"),
                    _card("material.policy.b", "policy", 97, 3, "B"),
                ],
            },
        },
    )
    res = StructuredV1ContextStrategy().build(req)
    full = "\n".join(res.system_blocks)
    # Same priority(97) should place seq=3 before seq=2 after sorting.
    assert full.index("material.policy.b") < full.index("material.policy.a")
