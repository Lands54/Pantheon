from __future__ import annotations

from gods.janus.facade import ContextBuildRequest, StructuredV1ContextStrategy


def test_janus_materials_are_cardized_and_linearized():
    req = ContextBuildRequest(
        project_id="unit_janus_cardized_materials",
        agent_id="alpha",
        state={"messages": [], "context": "objective"},
        directives="follow rules",
        local_memory="legacy memory should not be used directly",
        inbox_hint="check unread",
        phase_name="react_graph",
        phase_block="phase block",
        tools_desc="- read\n- list",
        context_materials={
            "intent_seq_latest": 10,
            "card_buckets": {
                "profile": [{"card_id": "material.profile", "kind": "task", "priority": 100, "text": "[PROFILE]\\n# alpha profile", "source_intent_ids": [], "source_intent_seq_max": 10, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "task_state": [{"card_id": "material.task_state", "kind": "task", "priority": 98, "text": "[TASK_STATE]\\nobj", "source_intent_ids": [], "source_intent_seq_max": 10, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "mailbox": [{"card_id": "material.mailbox", "kind": "mailbox", "priority": 90, "text": "[MAILBOX]\\n[SUMMARY]\\n- unread=2", "source_intent_ids": [], "source_intent_seq_max": 10, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "events": [{"card_id": "material.trigger", "kind": "event", "priority": 92, "text": "[TRIGGER]\\nevent a", "source_intent_ids": [], "source_intent_seq_max": 10, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],

                "policy": [
                    {"card_id": "material.directives", "kind": "policy", "priority": 97, "text": "[DIRECTIVES]\\nfollow rules", "source_intent_ids": [], "source_intent_seq_max": 10, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0},
                    {"card_id": "material.phase", "kind": "policy", "priority": 96, "text": "[PHASE]\\nreact_graph", "source_intent_ids": [], "source_intent_seq_max": 10, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0},
                    {"card_id": "material.tools", "kind": "policy", "priority": 94, "text": "[TOOLS]\\n- read", "source_intent_ids": [], "source_intent_seq_max": 10, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0},
                ],
            },
        },
    )
    res = StructuredV1ContextStrategy().build(req)
    full = "\n\n".join(res.system_blocks)
    assert "# CARD_CONTEXT" in full
    assert "[task:material.profile]" in full
    assert "[task:material.task_state]" in full
    assert "[mailbox:material.mailbox]" in full
    assert "[policy:material.directives]" in full
    assert "[CHRONICLE]" not in full
    assert "# CONTEXT_INDEX" not in full
