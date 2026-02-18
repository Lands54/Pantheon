"""Tool gateway use-case service."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods.interaction import facade as interaction_facade
from gods.mnemosyne import facade as mnemosyne_facade
from gods.tools import facade as tools_facade


class ToolGatewayService:
    def list_agents(self, project_id: str | None = None, caller_id: str = "external") -> dict[str, Any]:
        pid = resolve_project(project_id)
        text = tools_facade.list_agents.invoke({"caller_id": caller_id, "project_id": pid})
        return {"project_id": pid, "result": text}

    def check_inbox(self, project_id: str | None, agent_id: str) -> dict[str, Any]:
        pid = resolve_project(project_id)
        agent_dir = Path("projects") / pid / "agents" / agent_id
        if not agent_dir.exists():
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in '{pid}'")
        text = tools_facade.check_inbox.invoke({"caller_id": agent_id, "project_id": pid})
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if not isinstance(parsed, list):
            parsed = []
        return {"project_id": pid, "agent_id": agent_id, "result": text, "messages": parsed}

    def check_outbox(
        self,
        project_id: str | None,
        agent_id: str,
        to_id: str = "",
        status: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        agent_dir = Path("projects") / pid / "agents" / agent_id
        if not agent_dir.exists():
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in '{pid}'")
        text = tools_facade.check_outbox.invoke(
            {
                "caller_id": agent_id,
                "project_id": pid,
                "to_id": to_id,
                "status": status,
                "limit": int(limit),
            }
        )
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        return {"project_id": pid, "agent_id": agent_id, "result": text, "items": parsed}

    def send_message(
        self,
        project_id: str | None,
        from_id: str,
        to_id: str,
        title: str,
        message: str,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        from_dir = Path("projects") / pid / "agents" / from_id
        to_dir = Path("projects") / pid / "agents" / to_id
        if not from_dir.exists():
            raise HTTPException(status_code=404, detail=f"Sender agent '{from_id}' not found in '{pid}'")
        if not to_dir.exists():
            raise HTTPException(status_code=404, detail=f"Target agent '{to_id}' not found in '{pid}'")
        if not str(title or "").strip():
            raise HTTPException(status_code=400, detail="title is required")
        attachment_ids = [str(x).strip() for x in list(attachments or []) if str(x).strip()]
        for aid in attachment_ids:
            if not mnemosyne_facade.is_valid_artifact_id(aid):
                raise HTTPException(status_code=400, detail=f"invalid attachment id: {aid}")
            try:
                ref = mnemosyne_facade.head_artifact(aid, from_id, pid)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"attachment not accessible: {aid}: {e}") from e
            if str(getattr(ref, "scope", "")) != "agent":
                raise HTTPException(status_code=400, detail=f"attachment must be agent-scope: {aid}")
        weights = angelia_facade.get_priority_weights(pid)
        trigger = angelia_facade.is_mail_event_wakeup_enabled(pid)
        row = interaction_facade.submit_message_event(
            project_id=pid,
            to_id=to_id,
            sender_id=from_id,
            title=title,
            content=message,
            msg_type="private",
            trigger_pulse=trigger,
            priority=int(weights.get("mail_event", 100)),
            event_type="interaction.message.sent",
            attachments=attachment_ids,
        )
        return {
            "project_id": pid,
            "from_id": from_id,
            "to_id": to_id,
            "attachments_count": len(attachment_ids),
            **row,
        }


tool_gateway_service = ToolGatewayService()
