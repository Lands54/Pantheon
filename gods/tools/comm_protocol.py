"""Protocol recording communication tool."""
from __future__ import annotations

import re

from langchain.tools import tool

from gods.tools.comm_common import format_comm_error


@tool
def record_protocol(
    topic: str,
    relation: str,
    object: str,
    clause: str,
    counterparty: str = "",
    status: str = "agreed",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Register executable protocol clause in Hermes bus."""
    try:
        if not topic.strip() or not relation.strip() or not object.strip() or not clause.strip():
            return format_comm_error(
                "Protocol Error",
                "topic/relation/object/clause cannot be empty.",
                "Provide all required protocol fields before recording.",
                caller_id,
                project_id,
            )

        from gods.hermes import hermes_service
        from gods.hermes.errors import HermesError
        from gods.hermes.models import ProtocolSpec
        from gods.hermes.policy import allow_agent_tool_provider

        relation_tool_map = {
            "read": "read_file",
            "read_file": "read_file",
            "write": "write_file",
            "write_file": "write_file",
            "replace_content": "replace_content",
            "insert_content": "insert_content",
            "multi_replace": "multi_replace",
            "list": "list_dir",
            "list_dir": "list_dir",
            "run": "run_command",
            "run_command": "run_command",
            "send": "send_message",
            "send_message": "send_message",
            "check_inbox": "check_inbox",
            "call_protocol": "call_protocol",
        }
        tool_name = relation_tool_map.get(relation.strip().lower(), relation.strip())

        allowed_tools = {
            "read_file",
            "write_file",
            "replace_content",
            "insert_content",
            "multi_replace",
            "list_dir",
            "run_command",
            "send_message",
            "check_inbox",
            "call_protocol",
            "register_protocol",
            "check_protocol_job",
            "list_protocols",
        }
        if tool_name not in allowed_tools:
            return format_comm_error(
                "Protocol Error",
                f"Cannot map relation '{relation}' to an executable tool.",
                "Use relation as a concrete tool name, e.g. run_command / write_file / call_protocol.",
                caller_id,
                project_id,
            )

        def _slug(v: str) -> str:
            text = (v or "").strip().lower()
            text = re.sub(r"[^a-z0-9_]+", "_", text)
            text = re.sub(r"_+", "_", text).strip("_")
            return text

        topic_slug = _slug(topic)
        object_slug = _slug(object)
        if not topic_slug or not object_slug:
            return format_comm_error(
                "Protocol Error",
                "topic/object cannot be normalized into valid protocol name segments.",
                "Use alphanumeric topic/object, e.g. ecosystem and simulator.",
                caller_id,
                project_id,
            )

        protocol_name = f"{topic_slug}.{object_slug}"
        spec = ProtocolSpec(
            name=protocol_name,
            version="1.0.0",
            description=f"{clause.strip()} (counterparty={counterparty.strip()}, status={status.strip()})",
            mode="both",
            provider={
                "type": "agent_tool",
                "project_id": project_id,
                "agent_id": caller_id,
                "tool_name": tool_name,
            },
            request_schema={"type": "object"},
            response_schema={
                "type": "object",
                "required": ["result"],
                "properties": {"result": {"type": "string"}},
            },
        )
        if not allow_agent_tool_provider(project_id):
            return format_comm_error(
                "Protocol Error",
                "agent_tool provider is disabled by policy for this project.",
                "Use register_protocol with provider_type=http, or enable hermes_allow_agent_tool_provider.",
                caller_id,
                project_id,
            )
        hermes_service.register(project_id, spec)
        return f"Protocol registered: {protocol_name}@1.0.0"
    except HermesError as e:
        return format_comm_error(
            "Protocol Error",
            f"{e.code}: {e.message}",
            "Adjust relation/tool mapping and retry record_protocol.",
            caller_id,
            project_id,
        )
    except Exception as e:
        return format_comm_error(
            "Protocol Error",
            str(e),
            "Retry record_protocol and verify protocol directory is writable.",
            caller_id,
            project_id,
        )
