"""
Shared tool-policy helpers for agent/runtime/scheduler decisions.
"""
from __future__ import annotations

from gods.config import runtime_config


SOCIAL_TOOLS = {
    "check_inbox",
    "send_message",
    "send_to_human",
    "post_to_synod",
    "abstain_from_synod",
    "record_protocol",
    "list_agents",
}


def get_disabled_tools(project_id: str, agent_id: str) -> set[str]:
    proj = runtime_config.projects.get(project_id)
    if not proj:
        return set()
    settings = proj.agent_settings.get(agent_id)
    if not settings:
        return set()
    return set(settings.disabled_tools or [])


def is_tool_disabled(project_id: str, agent_id: str, tool_name: str) -> bool:
    return tool_name in get_disabled_tools(project_id, agent_id)


def is_social_disabled(project_id: str, agent_id: str) -> bool:
    disabled = get_disabled_tools(project_id, agent_id)
    return (SOCIAL_TOOLS & disabled) == SOCIAL_TOOLS

