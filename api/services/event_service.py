"""Unified event-bus use-case service."""
from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods import events as events_bus
from gods.interaction import facade as interaction_facade
from gods.runtime import facade as runtime_facade

EVENT_MESSAGE_SENT = "interaction.message.sent"
EVENT_MESSAGE_READ = "interaction.message.read"
EVENT_HERMES_NOTICE = "interaction.hermes.notice"
EVENT_DETACH_NOTICE = "interaction.detach.notice"
EVENT_AGENT_TRIGGER = "interaction.agent.trigger"


class EventService:
    def catalog(self, project_id: str | None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        base = events_bus.event_catalog()
        known = {str(x.get("event_type", "")) for x in base}
        seen = {
            str(x.event_type)
            for x in events_bus.list_events(pid, limit=5000)
            if str(getattr(x, "event_type", "")).strip()
        }
        dynamic: list[dict[str, Any]] = []
        for et in sorted(seen - known):
            dynamic.append(
                {
                    "event_type": et,
                    "domain": "unknown",
                    "title": "未登记事件",
                    "description": "该事件在运行中出现，但尚未在事件目录中登记。",
                    "feeds_llm": None,
                    "llm_note": "未知，请补充事件目录定义。",
                }
            )
        return {"project_id": pid, "items": base + dynamic}

    def submit(
        self,
        project_id: str | None,
        domain: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        priority: int | None = None,
        dedupe_key: str = "",
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        domain = str(domain or "").strip().lower()
        event_type = str(event_type or "").strip().lower()
        payload = payload or {}
        pri = int(priority if priority is not None else 50)

        if not domain or not event_type:
            raise HTTPException(status_code=400, detail="domain and event_type are required")

        # Interaction path (single entry for agent interactions).
        if domain == "interaction" and event_type in {
            EVENT_MESSAGE_SENT,
            EVENT_MESSAGE_READ,
            EVENT_HERMES_NOTICE,
            EVENT_DETACH_NOTICE,
            EVENT_AGENT_TRIGGER,
        }:
            if event_type == EVENT_MESSAGE_READ:
                agent_id = str(payload.get("agent_id", "")).strip()
                event_ids = [str(x) for x in (payload.get("event_ids", []) or []) if str(x).strip()]
                if not agent_id or not event_ids:
                    raise HTTPException(status_code=400, detail="interaction.message.read requires payload.agent_id and payload.event_ids")
                return interaction_facade.submit_read_event(
                    project_id=pid,
                    agent_id=agent_id,
                    event_ids=event_ids,
                    priority=pri,
                    dedupe_key=dedupe_key,
                )
            if event_type == EVENT_AGENT_TRIGGER:
                raise HTTPException(
                    status_code=410,
                    detail="interaction.agent.trigger is restricted; use angelia timer/manual/system events",
                )
            if event_type == EVENT_HERMES_NOTICE:
                targets = [str(x).strip() for x in (payload.get("targets", []) or []) if str(x).strip()]
                if targets:
                    sender_id = str(payload.get("sender_id", "Hermes")).strip() or "Hermes"
                    title = str(payload.get("title", "Hermes Notice")).strip() or "Hermes Notice"
                    content = str(payload.get("content", ""))
                    msg_type = str(payload.get("msg_type", "contract_notice")).strip() or "contract_notice"
                    sent = interaction_facade.submit_hermes_notice(
                        project_id=pid,
                        targets=targets,
                        sender_id=sender_id,
                        title=title,
                        content=content,
                        msg_type=msg_type,
                        trigger_pulse=bool(payload.get("trigger_pulse", True)),
                        priority=pri,
                        dedupe_prefix=dedupe_key or "hermes_notice",
                    )
                    return {
                        "event_id": "",
                        "event_type": EVENT_HERMES_NOTICE,
                        "state": "queued",
                        "project_id": pid,
                        "agent_id": "",
                        "wakeup_sent": bool(sent),
                        "meta": {"sent_targets": sent},
                    }
            if event_type == EVENT_DETACH_NOTICE:
                aid = str(payload.get("agent_id", "")).strip()
                title = str(payload.get("title", "Detach Notice")).strip() or "Detach Notice"
                content = str(payload.get("content", ""))
                if not aid:
                    raise HTTPException(status_code=400, detail="interaction.detach.notice requires payload.agent_id")
                return interaction_facade.submit_detach_notice(
                    project_id=pid,
                    agent_id=aid,
                    title=title,
                    content=content,
                    msg_type=str(payload.get("msg_type", "detach_notice")),
                    trigger_pulse=bool(payload.get("trigger_pulse", True)),
                    priority=pri,
                    dedupe_key=dedupe_key,
                )
            # message.sent/hermes.notice single-target path.
            to_id = str(payload.get("to_id", "")).strip()
            sender_id = str(payload.get("sender_id", "")).strip()
            title = str(payload.get("title", "")).strip()
            content = str(payload.get("content", ""))
            msg_type = str(payload.get("msg_type", "private")).strip() or "private"
            attachments = [str(x).strip() for x in list(payload.get("attachments", []) or []) if str(x).strip()]
            if not to_id or not sender_id or not title:
                raise HTTPException(status_code=400, detail="interaction.message.sent requires payload.to_id, payload.sender_id, payload.title")
            return interaction_facade.submit_message_event(
                project_id=pid,
                to_id=to_id,
                sender_id=sender_id,
                title=title,
                content=content,
                msg_type=msg_type,
                trigger_pulse=bool(payload.get("trigger_pulse", True)),
                priority=pri,
                dedupe_key=dedupe_key,
                event_type=event_type,
                attachments=attachments,
            )

        # Mail path is removed from public entry in zero-compat mode.
        if domain == "iris" and event_type in {"mail_event", "mail_deliver_event", "mail_ack_event"}:
            raise HTTPException(status_code=410, detail="iris mail events moved to domain=interaction,event_type=interaction.message.sent")

        # Angelia scheduling path
        if domain == "angelia" and event_type in {"timer", "manual", "system"}:
            agent_id = str(payload.get("agent_id", "")).strip()
            if not agent_id:
                raise HTTPException(status_code=400, detail="angelia events require payload.agent_id")
            row = angelia_facade.enqueue_event(
                project_id=pid,
                agent_id=agent_id,
                event_type=event_type,
                payload=payload,
                priority=pri,
                dedupe_key=dedupe_key,
            )
            return {
                "project_id": pid,
                "domain": "angelia",
                "event_type": event_type,
                "event_id": row.get("event_id", ""),
                "state": row.get("state", "queued"),
                "agent_id": agent_id,
                "wakeup_sent": True,
                "meta": row,
            }

        # Detach eventized path
        if domain == "runtime" and event_type == "detach_submitted_event":
            agent_id = str(payload.get("agent_id", "")).strip()
            command = str(payload.get("command", "")).strip()
            if not agent_id or not command:
                raise HTTPException(status_code=400, detail="detach_submitted_event requires payload.agent_id and payload.command")
            try:
                row = runtime_facade.detach_submit(project_id=pid, agent_id=agent_id, command=command)
            except runtime_facade.DetachError as e:
                raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}") from e
            rec = events_bus.EventRecord.create(
                project_id=pid,
                domain="runtime",
                event_type="detach_submitted_event",
                priority=pri,
                payload={"agent_id": agent_id, "command": command, **row},
                dedupe_key=dedupe_key,
                max_attempts=max_attempts,
                meta={"api": True},
            )
            events_bus.append_event(rec)
            events_bus.transition_state(pid, rec.event_id, events_bus.EventState.DONE)
            return {
                "project_id": pid,
                "domain": "runtime",
                "event_type": "detach_submitted_event",
                "event_id": rec.event_id,
                "state": "done",
                "agent_id": agent_id,
                "wakeup_sent": False,
                "meta": row,
            }

        # Generic append for unsupported but valid new events.
        rec = events_bus.EventRecord.create(
            project_id=pid,
            domain=domain,
            event_type=event_type,
            priority=pri,
            payload=payload,
            dedupe_key=dedupe_key,
            max_attempts=max_attempts,
            meta={"api": True},
        )
        rec = events_bus.append_event(rec)
        aid = str((payload or {}).get("agent_id", "")).strip()
        woke = False
        if domain in {"iris", "angelia"} and aid:
            try:
                angelia_facade.wake_agent(pid, aid)
                woke = True
            except Exception:
                woke = False
        return {
            "project_id": pid,
            "domain": domain,
            "event_type": event_type,
            "event_id": rec.event_id,
            "state": rec.state.value,
            "agent_id": aid,
            "wakeup_sent": woke,
            "meta": {"queued_at": rec.created_at},
        }

    def list(
        self,
        project_id: str | None,
        domain: str = "",
        event_type: str = "",
        state: str = "",
        limit: int = 100,
        agent_id: str = "",
    ) -> dict[str, Any]:
        pid = resolve_project(project_id)
        st = events_bus.EventState(state) if state else None
        rows = [
            x.to_dict()
            for x in events_bus.list_events(
                project_id=pid,
                domain=domain,
                event_type=event_type,
                state=st,
                limit=max(1, min(limit, 1000)),
                agent_id=agent_id,
            )
        ]
        return {"project_id": pid, "items": rows}

    def retry(self, project_id: str | None, event_id: str) -> dict[str, Any]:
        pid = resolve_project(project_id)
        ok = events_bus.retry_event(pid, event_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"event '{event_id}' not retryable/not found")
        return {"project_id": pid, "event_id": event_id, "status": "queued"}

    def ack(self, project_id: str | None, event_id: str) -> dict[str, Any]:
        pid = resolve_project(project_id)
        ok = events_bus.transition_state(pid, event_id, events_bus.EventState.DONE)
        if not ok:
            raise HTTPException(status_code=404, detail=f"event '{event_id}' not ack-able/not found")
        return {"project_id": pid, "event_id": event_id, "status": "done"}

    def reconcile(self, project_id: str | None, timeout_sec: int = 60) -> dict[str, Any]:
        pid = resolve_project(project_id)
        recovered = events_bus.reconcile_stale(pid, timeout_sec=timeout_sec)
        detach = None
        try:
            detach = runtime_facade.detach_reconcile(project_id=pid)
        except Exception:
            detach = None
        return {"project_id": pid, "recovered": int(recovered), "detach": detach, "at": time.time()}

    def metrics(self, project_id: str | None) -> dict[str, Any]:
        pid = resolve_project(project_id)
        by_state: dict[str, int] = {}
        rows = events_bus.list_events(pid, limit=5000)
        for row in rows:
            by_state[row.state.value] = by_state.get(row.state.value, 0) + 1
        return {
            "project_id": pid,
            "event_bus": {
                "total": len(rows),
                "by_state": by_state,
            },
            "angelia": angelia_facade.metrics_snapshot(),
        }


event_service = EventService()
