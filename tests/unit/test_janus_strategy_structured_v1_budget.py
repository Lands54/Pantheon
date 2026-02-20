from langchain_core.messages import HumanMessage

from gods.janus.facade import ContextBuildRequest, StructuredV1ContextStrategy


def test_structured_v1_uses_dynamic_recent_budget_not_fixed_8(tmp_path, monkeypatch):
    req = ContextBuildRequest(
        project_id="p_struct_budget",
        agent_id="a",
        state={"messages": [HumanMessage(content=("x" * 50), name="h") for _ in range(30)], "context": "obj"},
        directives="# a",
        local_memory="local mem",
        inbox_hint="inbox",
        phase_name="act",
        tools_desc="- [[list(path)]]",
        context_cfg={
            "token_budget_total": 2000,
        },
        context_materials={
            "intent_seq_latest": 1,
            "card_buckets": {
                "profile": [{"card_id": "material.profile", "kind": "task", "priority": 100, "text": "[PROFILE]\\na", "source_intent_ids": [], "source_intent_seq_max": 1, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "task_state": [{"card_id": "material.task_state", "kind": "task", "priority": 98, "text": "[TASK]\\nobj", "source_intent_ids": [], "source_intent_seq_max": 1, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "mailbox": [{"card_id": "material.mailbox", "kind": "mailbox", "priority": 90, "text": "[MAILBOX]\\nnone", "source_intent_ids": [], "source_intent_seq_max": 1, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "events": [{"card_id": "material.trigger", "kind": "event", "priority": 92, "text": "[TRIGGER]\\nnone", "source_intent_ids": [], "source_intent_seq_max": 1, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "policy": [{"card_id": "material.phase", "kind": "policy", "priority": 96, "text": "[PHASE]\\nact", "source_intent_ids": [], "source_intent_seq_max": 1, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
            },
        },
    )
    res = StructuredV1ContextStrategy().build(req)
    assert res.strategy_used == "structured_v1"
    full = "\n\n".join(res.system_blocks)
    assert "# CARD_CONTEXT" in full
    assert "[TASK]" in full
    assert "[CHRONICLE]" not in full
    assert "# CONTEXT_INDEX" not in full
