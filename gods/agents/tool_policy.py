"""
Shared tool-policy helpers for agent/runtime/scheduler decisions.
"""
from __future__ import annotations

from gods.config import runtime_config


SOCIAL_TOOLS = {
    "check_inbox",
    "send_message",
    "post_to_synod",
    "abstain_from_synod",
    "list_agents",
}


def get_disabled_tools(project_id: str, agent_id: str) -> set[str]:
    """
    Retrieves the set of disabled tool names for a specific agent in a given project.
    """
    proj = runtime_config.projects.get(project_id)
    if not proj:
        return set()
    settings = proj.agent_settings.get(agent_id)
    if not settings:
        return set()
    return set(settings.disabled_tools or [])


def is_tool_disabled(project_id: str, agent_id: str, tool_name: str) -> bool:
    """
    Checks if a specific tool is disabled for an agent in a given project.
    """
    return tool_name in get_disabled_tools(project_id, agent_id)


def is_social_disabled(project_id: str, agent_id: str) -> bool:
    """
    Checks if all social tools are disabled for an agent in a given project.
    """
    disabled = get_disabled_tools(project_id, agent_id)
    return (SOCIAL_TOOLS & disabled) == SOCIAL_TOOLS
