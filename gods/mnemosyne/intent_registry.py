"""Registry for strict memory intent key expansion."""
from __future__ import annotations


# Keep this list aligned with exposed agent tools.
# This registry intentionally avoids importing gods.tools to keep Mnemosyne decoupled.
TOOL_INTENT_NAMES: list[str] = [
    "check_inbox",
    "check_outbox",
    "send_message",
    "finalize",
    "read",
    "write_file",
    "replace_content",
    "insert_content",
    "run_command",
    "run_command_detach",
    "detach_list",
    "detach_stop",
    "post_to_synod",
    "abstain_from_synod",
    "list_agents",
    "multi_replace",
    "list",
    "register_contract",
    "commit_contract",
    "list_contracts",
    "disable_contract",
    "reserve_port",
    "release_port",
    "list_port_leases",
    "mnemo_write_agent",
    "mnemo_list_agent",
    "mnemo_read_agent",
    "upload_artifact",
]


def tool_intent_names() -> list[str]:
    return sorted(set([str(x).strip() for x in TOOL_INTENT_NAMES if str(x).strip()]))


BASE_INTENT_KEYS: list[str] = [
    "event.mail_event",
    "event.timer",
    "event.manual",
    "event.system",
    "event.interaction.message.sent",
    "event.interaction.message.read",
    "event.interaction.hermes.notice",
    "event.interaction.detach.notice",
    "event.interaction.agent.trigger",
    "event.hermes_protocol_invoked_event",
    "event.hermes_job_updated_event",
    "event.hermes_contract_registered_event",
    "event.hermes_contract_committed_event",
    "event.hermes_contract_disabled_event",
    "event.detach_submitted_event",
    "event.detach_started_event",
    "event.detach_stopping_event",
    "event.detach_stopped_event",
    "event.detach_failed_event",
    "event.detach_reconciled_event",
    "event.detach_lost_event",
    "inbox.received.unread",
    "inbox.notice.contract_commit_notice",
    "inbox.notice.contract_fully_committed",
    "inbox.read_ack",
    "outbox.sent.pending",
    "outbox.sent.delivered",
    "outbox.sent.handled",
    "outbox.sent.failed",
    "inbox.section.summary",
    "inbox.section.recent_read",
    "inbox.section.recent_send",
    "inbox.section.inbox_unread",
    "llm.response",
    "agent.mode.freeform",
    "agent.safety.tool_loop_cap",
    "agent.event.injected",
    "phase.retry.reason",
    "phase.retry.act",
    "phase.retry.observe",
]


def registered_intent_keys() -> list[str]:
    keys = list(BASE_INTENT_KEYS)
    for tool_name in tool_intent_names():
        keys.append(f"tool.{tool_name}.ok")
        keys.append(f"tool.{tool_name}.error")
        keys.append(f"tool.{tool_name}.blocked")
    return sorted(set(keys))


def is_registered_intent_key(intent_key: str) -> bool:
    key = str(intent_key or "").strip()
    if not key:
        return False
    return key in set(registered_intent_keys())
