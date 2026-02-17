"""Unified event-bus use-case service."""
from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException

from api.services.common.project_context import resolve_project
from gods.angelia import facade as angelia_facade
from gods import events as events_bus
from gods.iris import facade as iris_facade
from gods.runtime import facade as runtime_facade


class EventService:
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

        # Mail path
        if domain == "iris" and event_type in {"mail_event", "mail_deliver_event", "mail_ack_event"}:
            agent_id = str(payload.get("agent_id", "")).strip()
            title = str(payload.get("title", "")).strip()
            content = str(payload.get("content", ""))
            sender = str(payload.get("sender", "system"))
            msg_type = str(payload.get("msg_type", "private"))
            if not agent_id or not title:
                raise HTTPException(status_code=400, detail="mail_event requires payload.agent_id and payload.title")
            row = iris_facade.enqueue_message(
                project_id=pid,
                agent_id=agent_id,
                sender=sender,
                title=title,
                content=content,
                msg_type=msg_type,
                trigger_pulse=True,
                pulse_priority=pri,
            )
            return {
                "project_id": pid,
                "domain": "iris",
                "event_type": event_type,
                "event_id": row.get("mail_event_id", ""),
                "state": "queued",
                "agent_id": agent_id,
                "wakeup_sent": bool(row.get("wakeup_sent", False)),
                "meta": row,
            }

        # Angelia scheduling path
        if domain == "angelia" and event_type in {"timer_event", "manual_event", "system_event"}:
            mapped = {
                "timer_event": "timer",
                "manual_event": "manual",
                "system_event": "system",
            }[event_type]
            agent_id = str(payload.get("agent_id", "")).strip()
            if not agent_id:
                raise HTTPException(status_code=400, detail="angelia events require payload.agent_id")
            row = angelia_facade.enqueue_event(
                project_id=pid,
                agent_id=agent_id,
                event_type=mapped,
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
        ok = events_bus.transition_state(pid, event_id, events_bus.EventState.HANDLED)
        if not ok:
            raise HTTPException(status_code=404, detail=f"event '{event_id}' not ack-able/not found")
        return {"project_id": pid, "event_id": event_id, "status": "handled"}

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
