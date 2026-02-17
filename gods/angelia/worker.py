"""Per-agent Angelia worker."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from . import policy, store
from gods.angelia.mailbox import angelia_mailbox
from gods.angelia.metrics import angelia_metrics
from gods.angelia.models import AgentRunState, AgentRuntimeStatus
from gods import events as events_bus
from gods.iris.facade import ack_handled, fetch_inbox_context, fetch_mailbox_intents, has_pending
from gods.mnemosyne.facade import intent_from_angelia_event
from gods.mnemosyne import record_intent
from gods.angelia.pulse.policy import get_inject_budget

_INTERACTION_HANDLERS_READY = False


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


def _resolve_handler(event_type: str) -> events_bus.EventHandler:
    meta = events_bus.event_meta(event_type)
    if meta is None:
        raise ValueError(f"EVENT_CATALOG_MISSING: event_type '{event_type}' is not registered in catalog")
    if meta.get("feeds_llm") is False:
        raise ValueError(f"EVENT_LLM_DISALLOWED: event_type '{event_type}' is marked feeds_llm=false")
    h = events_bus.get_handler(event_type)
    if h is not None:
        return h
    # All Angelia scheduler event types default to one agent pulse handler.
    events_bus.register_handler(event_type, _DEFAULT_AGENT_RUN_HANDLER)
    return _DEFAULT_AGENT_RUN_HANDLER


def _run_agent(
    project_id: str,
    agent_id: str,
    reason: str,
    pulse_id: str,
    event_records: list[events_bus.EventRecord] | None = None,
) -> dict:
    from gods.agents.base import GodAgent

    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    
    # 1. Trigger Events (Batch)
    trigger_intents: list[MemoryIntent] = []
    if event_records:
        for rec in event_records:
            try:
                trigger_intents.append(intent_from_angelia_event(rec, stage="trigger"))
            except Exception:
                # If rendering fails, we try a fallback intent but continue
                # Actually intent_from_angelia_event shouldn't raise usually, but safeguard
                pass
    else:
        # Fallback for manual/legacy calls without record
        legacy = intent_from_angelia_event(
            events_bus.EventRecord(
                project_id=project_id, 
                event_type="manual_pulse", 
                payload={"reason": reason, "agent_id": agent_id}
            ), 
            stage="trigger"
        )
        trigger_intents.append(legacy)

    # 2. Mailbox Events
    budget = get_inject_budget(project_id)
    mailbox_intents = fetch_mailbox_intents(project_id, agent_id, budget)
    
    # Extract IDs for ACK later
    delivered_ids = []
    for intent in mailbox_intents:
        if intent.intent_key.startswith("inbox.received") or intent.intent_key.startswith("inbox.notice"):
             mid = intent.payload.get("message_id")
             if mid:
                 delivered_ids.append(mid)

    # 3. State Construction
    # We DO NOT render text here. We pass intents to the agent state.
    state = {
        "project_id": project_id,
        "messages": [], # Janus will build history. No synthetic SystemMessages!
        "context": "", # Deprecated legacy context string
        "next_step": "",
        "triggers": trigger_intents,
        "mailbox": mailbox_intents,
        "__pulse_meta": {
            "pulse_id": pulse_id,
            "reason": reason,
            "started_at": time.time(),
        },
        "__inbox_delivered_ids": delivered_ids,
    }

    new_state = agent.process(state)
    
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
            # allow pending inbox to trigger when queue event was missed
            if has_pending(project_id, agent_id):
                angelia_mailbox.notify(project_id, agent_id)
            continue

        while not stop_event.is_set():
            st = _status(project_id, agent_id)
            now = time.time()
            cooldown_until = max(float(st.cooldown_until or 0.0), float(st.backoff_until or 0.0))
            
            # Batch Pick (Limit 10 for now)
            batch = store.pick_batch_events(
                project_id=project_id,
                agent_id=agent_id,
                now=now,
                cooldown_until=cooldown_until,
                preempt_types=preempt_types,
                limit=10,
            )

            if not batch:
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
            
            # on_pick semantics: technically we should call on_pick for each?
            for r in records:
                handler.on_pick(r)

            start = time.time()
            try:
                for evt in batch:
                    record_intent(intent_from_angelia_event(evt, stage="processing"))
                
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
                    pulse_id = uuid.uuid4().hex[:12]
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
                    pulse_id = uuid.uuid4().hex[:12]
                    result = _run_agent(project_id, agent_id, reason, pulse_id, records)

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
                for evt in batch:
                    store.mark_done(project_id, evt.event_id)
                    record_intent(intent_from_angelia_event(evt, stage="done", extra_payload={"next_step": next_step}))

                # on_success for primary? or all?
                handler.on_success(records[0], result)
                
                _set_idle(st, cooldown)
                angelia_metrics.inc("event_done", len(batch))

            except Exception as e:
                # Batch Failure: Fail ALL.
                # In future we might want partial success, but for now atomic batch.
                handler.on_fail(records[0], e)
                for evt in batch:
                    state = store.mark_failed_or_requeue(
                        project_id,
                        evt.event_id,
                        error_code="WORKER_EXEC_ERROR",
                        error_message=str(e),
                        retry_delay_sec=min(30, max(2, 2 ** min(evt.attempt + 1, 5))),
                    )
                    try:
                        record_intent(intent_from_angelia_event(evt, stage="failed", extra_payload={"error": str(e)}))
                    except:
                        pass
                
                _set_error_backoff(st, str(e), delay_sec=5)
                angelia_metrics.inc("event_requeued", len(batch))

            finally:
                latency_ms = int((time.time() - start) * 1000)
                if latency_ms >= 0:
                    angelia_metrics.inc("pulse_runs")

    st = _status(project_id, agent_id)
    st.run_state = AgentRunState.STOPPED
    st.current_event_id = ""
    st.current_event_type = ""
    _save_status(st)
