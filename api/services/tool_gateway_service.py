"""Tool gateway use-case service."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods.hestia import facade as hestia_facade
from gods.interaction import facade as interaction_facade
from gods.mnemosyne import facade as mnemosyne_facade
from gods.mnemosyne.intent_builders import intent_from_tool_result
from gods.tools import facade as tools_facade

logger = logging.getLogger(__name__)


class ToolGatewayService:
    @staticmethod
    def _classify_status(result_text: str) -> str:
        text = str(result_text or "").strip().lower()
        if "divine restriction" in text or "policy block" in text:
            return "blocked"
        if text.startswith(
            (
                "tool execution error:",
                "tool error:",
                "path error:",
                "execution failed:",
                "execution timeout:",
                "execution backend error:",
                "territory error:",
                "command error:",
                "concurrency limit:",
            )
        ):
            return "error"
        return "ok"

    def _record_gateway_tool_intent(
        self,
        *,
        project_id: str,
        agent_id: str,
        tool_name: str,
        args: dict[str, Any],
        result_text: str,
    ) -> None:
        try:
            status = self._classify_status(result_text)
            intent = intent_from_tool_result(
                project_id=project_id,
                agent_id=agent_id,
                tool_name=tool_name,
                status=status,
                args=args,
                result=result_text,
            )
            mnemosyne_facade.record_intent(intent)
        except Exception as e:
            logger.warning("tool-gateway intent record failed: tool=%s project=%s agent=%s err=%s", tool_name, project_id, agent_id, e)

    def list_agents(self, project_id: str | None = None, caller_id: str = "external") -> dict[str, Any]:
        pid = resolve_project(project_id)
        args = {"path": "agent://all", "caller_id": caller_id, "project_id": pid, "page_size": 200, "page": 1}
        text = tools_facade.list.invoke(args)
        self._record_gateway_tool_intent(
            project_id=pid,
            agent_id=str(caller_id or "external"),
            tool_name="list",
            args=args,
            result_text=str(text),
        )
        return {"project_id": pid, "result": text}

    def check_inbox(self, project_id: str | None, agent_id: str) -> dict[str, Any]:
        pid = resolve_project(project_id)
        agent_dir = Path("projects") / pid / "agents" / agent_id
        if not agent_dir.exists():
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in '{pid}'")
        args = {"caller_id": agent_id, "project_id": pid}
        text = tools_facade.check_inbox.invoke(args)
        self._record_gateway_tool_intent(
            project_id=pid,
            agent_id=agent_id,
            tool_name="check_inbox",
            args=args,
            result_text=str(text),
        )
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
        args = {
            "caller_id": agent_id,
            "project_id": pid,
            "to_id": to_id,
            "status": status,
            "limit": int(limit),
        }
        text = tools_facade.check_outbox.invoke(args)
        self._record_gateway_tool_intent(
            project_id=pid,
            agent_id=agent_id,
            tool_name="check_outbox",
            args=args,
            result_text=str(text),
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
        if not hestia_facade.can_message(project_id=pid, from_id=from_id, to_id=to_id):
            raise HTTPException(status_code=403, detail=f"social graph denies route {from_id} -> {to_id}")
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
        self._record_gateway_tool_intent(
            project_id=pid,
            agent_id=from_id,
            tool_name="send_message",
            args={
                "to_id": to_id,
                "title": title,
                "message": message,
                "caller_id": from_id,
                "project_id": pid,
                "attachments": json.dumps(attachment_ids, ensure_ascii=False),
            },
            result_text=json.dumps(row, ensure_ascii=False),
        )
        return {
            "project_id": pid,
            "from_id": from_id,
            "to_id": to_id,
            "attachments_count": len(attachment_ids),
            **row,
        }


tool_gateway_service = ToolGatewayService()
