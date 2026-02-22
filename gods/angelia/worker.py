"""Per-agent Angelia worker."""
from __future__ import annotations

import threading
import time
import uuid
import logging
import hashlib
from dataclasses import dataclass

from . import policy, store
from gods.angelia.mailbox import angelia_mailbox
from gods.angelia.metrics import angelia_metrics
from gods.angelia.models import AgentRunState, AgentRuntimeStatus, AngeliaEvent
from gods import events as events_bus
from gods.iris.facade import ack_handled, has_pending, mark_as_delivered
from gods.mnemosyne.facade import (
    append_pulse_entry,
    intent_from_angelia_event,
    intent_from_inbox_read,
    intent_from_inbox_received,
    intent_from_outbox_status,
    intent_from_pulse_finish,
    intent_from_pulse_start,
)
from gods.mnemosyne import record_intent
from gods.angelia.pulse.policy import get_inject_budget
from gods.angelia import sync_council

_INTERACTION_HANDLERS_READY = False
logger = logging.getLogger(__name__)


def _ensure_interaction_handlers_registered():
    global _INTERACTION_HANDLERS_READY
    if _INTERACTION_HANDLERS_READY:
        return
    from gods.interaction.handler import register_handlers as _register_handlers

    _register_handlers()
    _INTERACTION_HANDLERS_READY = True


@dataclass
class WorkerContext:
    project_id: str
    agent_id: str
    stop_event: threading.Event


class _AgentRunHandler(events_bus.EventHandler):
    """Default Angelia handler: drive one agent pulse for event payload."""

    def on_process(self, record: events_bus.EventRecord) -> dict:
        payload = record.payload or {}
        project_id = record.project_id
        agent_id = str(payload.get("agent_id", "")).strip()
        if not agent_id:
            raise ValueError("event payload.agent_id is required")
        reason = str(payload.get("reason") or record.event_type)
        pulse_id = uuid.uuid4().hex[:12]
        return _run_agent(project_id, agent_id, reason, pulse_id, [record])


_DEFAULT_AGENT_RUN_HANDLER = _AgentRunHandler()


def _to_record(event) -> events_bus.EventRecord:
    row = event.to_dict()
    row.setdefault("domain", "angelia")
    payload = row.get("payload") or {}
    if "agent_id" not in payload:
        payload = {"agent_id": getattr(event, "agent_id", ""), **payload}
    row["payload"] = payload
    return events_bus.EventRecord.from_dict(row)


def _resolve_handler(event_type: str) -> events_bus.EventHandler | None:
    meta = events_bus.event_meta(event_type)
    if meta is None:
        raise ValueError(f"EVENT_CATALOG_MISSING: event_type '{event_type}' is not registered in catalog")
    h = events_bus.get_handler(event_type)
    if h is not None:
        return h
    # All Angelia scheduler event types default to one agent pulse handler.
    events_bus.register_handler(event_type, _DEFAULT_AGENT_RUN_HANDLER)
    return _DEFAULT_AGENT_RUN_HANDLER


def _record_event_lifecycle_intent(
    event: Any,
    stage: str,
    extra_payload: dict[str, Any] | None = None,
    *,
    pulse_id: str = "",
) -> None:
    try:
        try:
            intent = intent_from_angelia_event(
                event,
                stage=stage,
                extra_payload=extra_payload,
                pulse_id=pulse_id,
                origin="angelia",
            )
        except TypeError:
            # Keep test/mocking compatibility for builder stubs without new kwargs.
            intent = intent_from_angelia_event(
                event,
                stage=stage,
                extra_payload=extra_payload,
            )
        record_intent(intent)
    except Exception as e:
        logger.warning(
            "ANGELIA_EVENT_INTENT_RECORD_FAILED project=%s agent=%s event_id=%s stage=%s err=%s",
            str(getattr(event, "project_id", "") or ""),
            str(getattr(event, "agent_id", "") or ""),
            str(getattr(event, "event_id", "") or ""),
            str(stage or ""),
            str(e),
        )





def _resolve_mail_intent_key(msg_type: str) -> str:
    mt = str(msg_type or "").strip().lower()
    return {
        "contract_commit_notice": "inbox.notice.contract_commit_notice",
        "contract_fully_committed": "inbox.notice.contract_fully_committed",
    }.get(mt, "inbox.received.unread")


def _run_agent(
    project_id: str,
    agent_id: str,
    reason: str,
    pulse_id: str,
    event_records: list[events_bus.EventRecord],
) -> dict:
    from gods.agents.base import GodAgent

    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    claimed_records: list[events_bus.EventRecord] = []

    from gods.mnemosyne.facade import latest_intent_seq
    base_seq = latest_intent_seq(project_id, agent_id)

    try:
        start_event_ids = [str(getattr(r, "event_id", "") or "").strip() for r in list(event_records or []) if str(getattr(r, "event_id", "") or "").strip()]
        start_event_types = [str(getattr(r, "event_type", "") or "").strip() for r in list(event_records or []) if str(getattr(r, "event_type", "") or "").strip()]
        record_intent(
            intent_from_pulse_start(
                project_id=project_id,
                agent_id=agent_id,
                pulse_id=pulse_id,
                reason=reason,
                trigger_event_ids=start_event_ids,
                trigger_event_types=start_event_types,
                trigger_count=len(list(event_records or [])),
                base_intent_seq=base_seq,
                origin="angelia",
            )
        )
        append_pulse_entry(
            project_id,
            agent_id,
            pulse_id=pulse_id,
            kind="pulse.start",
            payload={
                "pulse_id": pulse_id,
                "reason": reason,
                "trigger_count": len(list(event_records or [])),
                "trigger_event_ids": start_event_ids,
                "trigger_event_types": start_event_types,
                "base_intent_seq": int(base_seq),
            },
            origin="angelia",
        )
    except Exception as exc:
        logger.warning(
            "PULSE_START_WRITE_FAIL: project=%s agent=%s pulse=%s err=%s",
            project_id, agent_id, pulse_id, exc,
        )
    
    # 1. Trigger Events (Batch)
    trigger_intents: list[MemoryIntent] = []
    delivered_ids: list[str] = []
    trigger_written = False
    for rec in event_records:
        try:
            et = str(getattr(rec, "event_type", ""))
            if et == "mail_event":
                payload = dict(getattr(rec, "payload", {}) or {})
                mt = str(payload.get("msg_type", ""))
                intent = intent_from_inbox_received(
                    project_id=project_id,
                    agent_id=agent_id,
                    title=str(payload.get("title", "")),
                    sender=str(payload.get("sender", "")),
                    message_id=str(getattr(rec, "event_id", "")),
                    content=str(payload.get("content", "")),
                    attachments=list(payload.get("attachments", [])),
                    msg_type=mt,
                    intent_key=_resolve_mail_intent_key(mt),
                    pulse_id=pulse_id,
                    origin="angelia",
                )
            elif et == "outbox_status_event":
                payload = dict(getattr(rec, "payload", {}) or {})
                intent = intent_from_outbox_status(
                    project_id=project_id,
                    agent_id=str(payload.get("agent_id", "") or ""),
                    to_agent_id=str(payload.get("to_agent_id", "") or ""),
                    title=str(payload.get("title", "") or ""),
                    message_id=str(payload.get("message_id", "") or ""),
                    status=str(payload.get("status", "") or ""),
                    error_message=str(payload.get("error_message", "") or ""),
                    attachments_count=int(payload.get("attachments_count", 0) or 0),
                    origin="angelia",
                )
            elif et == "inbox_read_event":
                payload = dict(getattr(rec, "payload", {}) or {})
                delivered_ids = [str(x).strip() for x in list(payload.get("delivered_ids", []) or []) if str(x).strip()]
                intent = intent_from_inbox_read(
                    project_id=project_id,
                    agent_id=str(payload.get("agent_id", "") or agent_id),
                    delivered_ids=delivered_ids,
                    count=int(payload.get("count", len(delivered_ids)) or len(delivered_ids)),
                )
            else:
                intent = intent_from_angelia_event(rec, stage="trigger", pulse_id=pulse_id, origin="angelia")
            try:
                if et == "mail_event":
                    append_pulse_entry(
                        project_id,
                        agent_id,
                        pulse_id=pulse_id,
                        kind="trigger.mail",
                        payload={
                            "event_id": str(getattr(rec, "event_id", "") or ""),
                            "msg_type": str(payload.get("msg_type", "") if et == "mail_event" else ""),
                            "title": str(payload.get("title", "") if et == "mail_event" else ""),
                            "sender": str(payload.get("sender", "") if et == "mail_event" else ""),
                            "content": str(payload.get("content", "") if et == "mail_event" else ""),
                            "message_id": str(getattr(rec, "event_id", "") or ""),
                        },
                        origin="angelia",
                    )
                    trigger_written = True
                else:
                    ev_payload = dict(getattr(rec, "payload", {}) or {})
                    append_pulse_entry(
                        project_id,
                        agent_id,
                        pulse_id=pulse_id,
                        kind="trigger.event",
                        payload={
                            "event_id": str(getattr(rec, "event_id", "") or ""),
                            "event_type": str(getattr(rec, "event_type", "") or ""),
                            "reason": str(ev_payload.get("reason", "") or getattr(rec, "event_type", "")),
                        },
                        origin="angelia",
                    )
                    trigger_written = True
            except Exception as exc:
                logger.warning(
                    "PULSE_TRIGGER_WRITE_FAIL: project=%s agent=%s pulse=%s err=%s",
                    project_id, agent_id, pulse_id, exc,
                )

            if intent is not None:
                res = record_intent(intent)
                setattr(intent, "intent_id", str(res.get("intent_id", "") or ""))
                setattr(intent, "intent_seq", int(res.get("intent_seq", 0) or 0))
                trigger_intents.append(intent)
            
            # If it's a mail event, mark it as delivered in Iris for the sender's awareness
            if et == "mail_event":
                mid = str(getattr(rec, "event_id", ""))
                delivered_ids.append(mid)
                try:
                    mark_as_delivered(project_id, mid)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning(
                "PULSE_TRIGGER_RECORD_FAIL: project=%s agent=%s pulse=%s err=%s",
                project_id, agent_id, pulse_id, exc,
            )

    # Hard invariant: trigger must come from real sources only.
    if not trigger_written:
        raise ValueError(
            f"PULSE_TRIGGER_MISSING: project={project_id} agent={agent_id} pulse={pulse_id} "
            "has no queue trigger"
        )

    # 2. Mailbox & State Construction
    state = {
        "project_id": project_id,
        "messages": [],
        "context": "",
        "next_step": "",
        "__pulse_meta": {
            "pulse_id": pulse_id,
            "reason": reason,
            "started_at": time.time(),
        },
        "__inbox_delivered_ids": delivered_ids,
        "__chaos_synced_seq": base_seq,
    }

    try:
        new_state = agent.process(state)
    except Exception as e:
        try:
            record_intent(
                intent_from_pulse_finish(
                    project_id=project_id,
                    agent_id=agent_id,
                    pulse_id=pulse_id,
                    next_step="error",
                    finalize_mode="",
                    tool_call_count=0,
                    tool_result_count=0,
                    llm_text_len=0,
                    origin="angelia",
                    error=f"{type(e).__name__}: {e}",
                )
            )
            append_pulse_entry(
                project_id,
                agent_id,
                pulse_id=pulse_id,
                kind="pulse.finish",
                payload={
                    "pulse_id": pulse_id,
                    "next_step": "error",
                    "finalize_mode": "",
                    "tool_call_count": 0,
                    "tool_result_count": 0,
                    "llm_text_len": 0,
                    "error": f"{type(e).__name__}: {e}",
                },
                origin="angelia",
            )
        except Exception as finish_exc:
            logger.warning(
                "PULSE_ERROR_FINISH_WRITE_FAIL: project=%s agent=%s pulse=%s err=%s",
                project_id, agent_id, pulse_id, finish_exc,
            )
        raise
    if isinstance(new_state, dict):
        new_state["__worker_claimed_events"] = [r.to_dict() for r in claimed_records]
    
    # ACK processed messages
    # We re-read from state just in case agent modified it, or we use our local list?
    # Agent might crash before processing.
    # Logic in old code: "delivered = list(new_state.get(...))"
    # So if agent crashes, new_state might be missing?
    # 'agent.process' returns state. If it crashes, it raises exception.
    # Exception is caught in worker_loop.
    # So we only ACK if process succeeds.
    delivered = list(new_state.get("__inbox_delivered_ids", []) or [])
    if delivered:
        ack_handled(project_id, delivered, agent_id)
    try:
        finalize_ctl = dict(new_state.get("finalize_control", {}) or {})
        finalize_mode = str(finalize_ctl.get("mode", "") or "").strip()
        llm_text = ""
        for msg in reversed(list(new_state.get("messages", []) or [])):
            content = getattr(msg, "content", None)
            if isinstance(content, str) and content.strip():
                llm_text = content
                break
        record_intent(
            intent_from_pulse_finish(
                project_id=project_id,
                agent_id=agent_id,
                pulse_id=pulse_id,
                next_step=str(new_state.get("next_step", "") or ""),
                finalize_mode=finalize_mode,
                tool_call_count=len(list(new_state.get("tool_calls", []) or [])),
                tool_result_count=len(list(new_state.get("tool_results", []) or [])),
                llm_text_len=len(llm_text),
                origin="angelia",
            )
        )
        append_pulse_entry(
            project_id,
            agent_id,
            pulse_id=pulse_id,
            kind="pulse.finish",
            payload={
                "pulse_id": pulse_id,
                "next_step": str(new_state.get("next_step", "") or ""),
                "finalize_mode": finalize_mode,
                "tool_call_count": len(list(new_state.get("tool_calls", []) or [])),
                "tool_result_count": len(list(new_state.get("tool_results", []) or [])),
                "llm_text_len": len(llm_text),
                "error": "",
            },
            origin="angelia",
        )
    except Exception as exc:
        logger.warning(
            "PULSE_FINISH_WRITE_FAIL: project=%s agent=%s pulse=%s err=%s",
            project_id, agent_id, pulse_id, exc,
        )
    return new_state


def _status(project_id: str, agent_id: str) -> AgentRuntimeStatus:
    return store.get_agent_status(project_id, agent_id)


def _save_status(st: AgentRuntimeStatus):
    st.updated_at = time.time()
    store.set_agent_status(st.project_id, st)


def _next_cooldown(project_id: str, next_step: str, empty_cycles: int) -> int:
    return policy.cooldown_from_next_step(project_id, next_step, empty_cycles)


def _finalize_quiescent_cooldown(project_id: str, result: dict) -> int:
    if not isinstance(result, dict):
        return 0
    ctl = result.get("__finalize_control")
    if not isinstance(ctl, dict):
        return 0
    mode = str(ctl.get("mode", "done") or "done").strip().lower()
    if mode != "quiescent":
        return 0
    if not policy.finalize_quiescent_enabled(project_id):
        return 0
    requested = ctl.get("sleep_sec", None)
    return int(policy.finalize_sleep_sec(project_id, requested if requested is not None else None))


def _set_running(st: AgentRuntimeStatus, event_id: str, event_type: str):
    st.run_state = AgentRunState.RUNNING
    st.current_event_id = event_id
    st.current_event_type = event_type
    st.last_wake_at = time.time()
    st.last_error = ""
    _save_status(st)


def _set_idle(st: AgentRuntimeStatus, cooldown_sec: int):
    now = time.time()
    st.run_state = AgentRunState.COOLDOWN if cooldown_sec > 0 else AgentRunState.IDLE
    st.cooldown_until = now + max(0, int(cooldown_sec))
    st.backoff_until = 0.0
    st.current_event_id = ""
    st.current_event_type = ""
    _save_status(st)


def _set_error_backoff(st: AgentRuntimeStatus, err: str, delay_sec: int):
    now = time.time()
    st.run_state = AgentRunState.ERROR_BACKOFF
    st.backoff_until = now + max(1, int(delay_sec))
    st.last_error = str(err)[:2000]
    st.current_event_id = ""
    st.current_event_type = ""
    _save_status(st)


def worker_loop(ctx: WorkerContext):
    _ensure_interaction_handlers_registered()
    project_id = ctx.project_id
    agent_id = ctx.agent_id
    stop_event = ctx.stop_event
    preempt_types = policy.cooldown_preempt_types(project_id)
    processing_timeout = policy.processing_timeout_sec(project_id)
    empty_cycles = 0

    st = _status(project_id, agent_id)
    st.run_state = AgentRunState.IDLE
    _save_status(st)

    while not stop_event.is_set():
        recovered = int(store.reclaim_stale_processing(project_id, processing_timeout) or 0)
        if recovered > 0:
            angelia_metrics.inc("QUEUE_STALL_TIMEOUT_RECOVERED_COUNT", recovered)

        woke = angelia_mailbox.wait(project_id, agent_id, timeout=1.0)
        if stop_event.is_set():
            break
        if not woke:
            # allow pending inbox or queued events to trigger when direct notify was missed
            if has_pending(project_id, agent_id) or store.has_queued(project_id, agent_id):
                angelia_mailbox.notify(project_id, agent_id)
            continue

        while not stop_event.is_set():
            st = _status(project_id, agent_id)
            now = time.time()
            cooldown_until = max(float(st.cooldown_until or 0.0), float(st.backoff_until or 0.0))
            
            # Batch pick size is runtime-configurable via angelia_pick_batch_size.
            try:
                pick_limit = policy.pick_batch_size(project_id)
                batch = store.pick_batch_events(
                    project_id=project_id,
                    agent_id=agent_id,
                    now=now,
                    cooldown_until=cooldown_until,
                    preempt_types=preempt_types,
                    limit=pick_limit,
                    force_after_sec=policy.force_pick_after_sec(project_id),
                )
            except Exception as e:
                _set_error_backoff(st, str(e), delay_sec=2)
                continue

            if not batch:
                try:
                    sync_council.tick(project_id, agent_id, has_queued=False)
                except Exception:
                    pass
                if now >= float(st.cooldown_until or 0.0) and now >= float(st.backoff_until or 0.0):
                    st.run_state = AgentRunState.IDLE
                    _save_status(st)
                break
            
            # Use the first event as the 'primary' for status tracking
            primary_event = batch[0]
            
            for evt in batch:
                store.mark_processing(project_id, evt.event_id)
            
            _set_running(st, primary_event.event_id, primary_event.event_type)
            angelia_metrics.inc("event_picked", len(batch))

            records = [_to_record(evt) for evt in batch]
            
            # We assume ALL events for an agent use the same handler (_AgentRunHandler).
            # If not, we should technically group them. 
            # But currently `_resolve_handler` returns DEFAULT_AGENT_RUN_HANDLER for all.
            handler = _resolve_handler(records[0].event_type)
            if handler is None:
                for evt in batch:
                    store.mark_done(project_id, evt.event_id)
                    _record_event_lifecycle_intent(evt, stage="done", extra_payload={"next_step": "skipped"})
                _set_idle(st, cooldown_sec=0)
                angelia_metrics.inc("event_done", len(batch))
                continue
            
            # on_pick semantics: technically we should call on_pick for each?
            for r in records:
                handler.on_pick(r)

            start = time.time()
            result: dict = {}
            pulse_id = uuid.uuid4().hex[:12]
            try:
                for evt in batch:
                    _record_event_lifecycle_intent(evt, stage="processing", pulse_id=pulse_id)
                
                # Combine payloads or just pick first reason?
                # The handler will now take list of records.
                # But `handler.on_process` signature takes ONE record.
                # We need to hack `_AgentRunHandler`'s on_process or call `_run_agent` directly.
                # `_AgentRunHandler` is internal private class.
                # Let's see `_AgentRunHandler.on_process` (lines 47).
                # It takes one record.
                # We should update `_AgentRunHandler` to accept batch, or custom logic here.
                # Since `_run_agent` is what we want, and `_AgentRunHandler` is a thin wrapper...
                # We can construct a synthetic 'BatchRecord' or just call `_run_agent` directly here?
                # No, `handler` abstraction is for future extensibility.
                
                # OPTION: Update `EventHandler.on_process` to support batch? No, base class change risky.
                # OPTION: Just pass the whole list in `payload` of a synthetic record?
                # OPTION: Special case for _AgentRunHandler since we know it.
                
                if isinstance(handler, _AgentRunHandler):
                    # Direct call to robust batch method
                    primary_rec = records[0]
                    reason = str((primary_rec.payload or {}).get("reason") or primary_rec.event_type)
                    result = _run_agent(project_id, agent_id, reason, pulse_id, records)
                else:
                    # Fallback for non-agent handlers: process one by one?
                    # This branch shouldn't happen for Agent worker loop if we only pick agent events.
                    # But if we support custom handlers...
                    # For safety, if handler is not our batch-aware one, process only first one and requeue rest?
                    # Or loop on_process?
                    # Let's loop on_process for now to be safe, though inefficient context.
                    # BUT `_run_agent` does a full pulse!
                    # So looping means N pulses.
                    # This defeats the purpose of batching.
                    # Since we are in `worker_loop` specifically for `Angelia`, we know we want `_run_agent`.
                    # Let's assume all picked events are for _run_agent.
                    primary_rec = records[0]
                    reason = str((primary_rec.payload or {}).get("reason") or primary_rec.event_type)
                    result = _run_agent(project_id, agent_id, reason, pulse_id, records)

                extra_events: list[AngeliaEvent] = []
                seen_ids = {str(evt.event_id) for evt in batch}
                for row in list(result.get("__worker_claimed_events", []) or []):
                    if not isinstance(row, dict):
                        continue
                    try:
                        evt = AngeliaEvent.from_dict(row)
                    except Exception:
                        continue
                    eid = str(getattr(evt, "event_id", "") or "")
                    if not eid or eid in seen_ids:
                        continue
                    seen_ids.add(eid)
                    extra_events.append(evt)

                all_events = list(batch) + extra_events
                next_step = str(result.get("next_step", "finish"))
                if next_step == "finish":
                    empty_cycles += 1
                else:
                    empty_cycles = 0
                
                cooldown = _next_cooldown(project_id, next_step, empty_cycles)
                quiescent_cooldown = _finalize_quiescent_cooldown(project_id, result)
                if quiescent_cooldown > 0:
                    cooldown = max(int(cooldown), int(quiescent_cooldown))
                
                # Mark ALL done
                for evt in all_events:
                    store.mark_done(project_id, evt.event_id)
                    _record_event_lifecycle_intent(
                        evt,
                        stage="done",
                        extra_payload={"next_step": next_step},
                        pulse_id=pulse_id,
                    )

                # on_success for primary? or all?
                handler.on_success(records[0], result)
                
                _set_idle(st, cooldown)
                angelia_metrics.inc("event_done", len(all_events))
                try:
                    sync_council.note_pulse_finished(project_id, agent_id)
                except Exception:
                    pass

            except Exception as e:
                # Batch Failure: Fail ALL.
                # In future we might want partial success, but for now atomic batch.
                handler.on_fail(records[0], e)
                all_events = list(batch)
                for row in list((result or {}).get("__worker_claimed_events", []) or []):
                    if not isinstance(row, dict):
                        continue
                    try:
                        evt = AngeliaEvent.from_dict(row)
                    except Exception:
                        continue
                    if str(evt.event_id) in {str(x.event_id) for x in all_events}:
                        continue
                    all_events.append(evt)
                for evt in all_events:
                    state = store.mark_failed_or_requeue(
                        project_id,
                        evt.event_id,
                        error_code="WORKER_EXEC_ERROR",
                        error_message=str(e),
                        retry_delay_sec=min(30, max(2, 2 ** min(evt.attempt + 1, 5))),
                    )
                    _record_event_lifecycle_intent(
                        evt,
                        stage="failed",
                        extra_payload={"error": str(e)},
                        pulse_id=pulse_id,
                    )
                
                _set_error_backoff(st, str(e), delay_sec=5)
                angelia_metrics.inc("event_requeued", len(all_events))
                try:
                    sync_council.note_pulse_finished(project_id, agent_id)
                except Exception:
                    pass

            finally:
                latency_ms = int((time.time() - start) * 1000)
                if latency_ms >= 0:
                    angelia_metrics.inc("pulse_runs")

    st = _status(project_id, agent_id)
    st.run_state = AgentRunState.STOPPED
    st.current_event_id = ""
    st.current_event_type = ""
    _save_status(st)
