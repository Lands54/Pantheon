"""Registry for strict memory intent key expansion."""
from __future__ import annotations


# Keep this list aligned with exposed agent tools.
# This registry intentionally avoids importing gods.tools to keep Mnemosyne decoupled.
TOOL_INTENT_NAMES: list[str] = [
    "check_inbox",
    "check_outbox",
    "send_message",
    "finalize",
    "read_file",
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
    "list_dir",
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
]


def tool_intent_names() -> list[str]:
    return sorted(set([str(x).strip() for x in TOOL_INTENT_NAMES if str(x).strip()]))
