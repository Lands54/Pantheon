from __future__ import annotations

from gods.janus.facade import ContextBuildRequest, StructuredV1ContextStrategy
from gods.mnemosyne.facade import intent_from_mailbox_section


def _section(section: str, rows: list[str]):
    return intent_from_mailbox_section("unit_janus_mailbox_sections", "alpha", section, rows)


def test_mailbox_sections_always_render():
    req = ContextBuildRequest(
        project_id="unit_janus_mailbox_sections",
        agent_id="alpha",
        state={
            "messages": [],
            "context": "obj",
            "mailbox": [
                _section("summary", ["- unread=2"]),
                _section("recent_read", ["- read a"]),
                _section("recent_send", ["- send b"]),
                _section("inbox_unread", ["- message c"]),
            ],
        },
        directives="d",
        local_memory="",
        inbox_hint="hint",
        phase_name="react_graph",
        tools_desc="- t",
    )
    res = StructuredV1ContextStrategy().build(req)
    full = "\n\n".join(res.system_blocks)
    assert "[SUMMARY]" in full
    assert "[RECENT READ]" in full
    assert "[RECENT SEND]" in full
    assert "[INBOX UNREAD]" in full
