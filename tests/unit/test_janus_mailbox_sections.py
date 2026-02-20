from __future__ import annotations

from gods.janus.facade import ContextBuildRequest, StructuredV1ContextStrategy


def test_mailbox_sections_always_render():
    req = ContextBuildRequest(
        project_id="unit_janus_mailbox_sections",
        agent_id="alpha",
        state={
            "messages": [],
            "context": "obj",
        },
        directives="d",
        local_memory="",
        inbox_hint="hint",
        phase_name="react_graph",
        tools_desc="- t",
        context_materials={
            "intent_seq_latest": 2,
            "card_buckets": {
                "profile": [{"card_id": "material.profile", "kind": "task", "priority": 100, "text": "[PROFILE]\\na", "source_intent_ids": [], "source_intent_seq_max": 2, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "task_state": [{"card_id": "material.task_state", "kind": "task", "priority": 98, "text": "[TASK]\\nobj", "source_intent_ids": [], "source_intent_seq_max": 2, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "mailbox": [{"card_id": "material.mailbox", "kind": "mailbox", "priority": 90, "text": "[MAILBOX]\\n[SUMMARY]\\n- unread=2\\n[RECENT READ]\\n- read a\\n[RECENT SEND]\\n- send b\\n[INBOX UNREAD]\\n- message c", "source_intent_ids": [], "source_intent_seq_max": 2, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "events": [{"card_id": "material.trigger", "kind": "event", "priority": 92, "text": "[TRIGGER]\\nnone", "source_intent_ids": [], "source_intent_seq_max": 2, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
                "policy": [{"card_id": "material.phase", "kind": "policy", "priority": 96, "text": "[PHASE]\\nreact_graph", "source_intent_ids": [], "source_intent_seq_max": 2, "derived_from_card_ids": [], "supersedes_card_ids": [], "compression_type": "", "meta": {}, "created_at": 1.0}],
            },
        },
    )
    res = StructuredV1ContextStrategy().build(req)
    full = "\n\n".join(res.system_blocks)
    assert "[SUMMARY]" in full
    assert "[RECENT READ]" in full
    assert "[RECENT SEND]" in full
    assert "[INBOX UNREAD]" in full
