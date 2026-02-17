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
from gods.iris.facade import ack_handled, fetch_inbox_context, has_pending
from gods.mnemosyne.facade import intent_from_angelia_event
from gods.mnemosyne import record_intent
from gods.prompts import prompt_registry
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
        return _run_agent(project_id, agent_id, reason, pulse_id)


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


def _run_agent(project_id: str, agent_id: str, reason: str, pulse_id: str) -> dict:
    from gods.agents.base import GodAgent

    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    pulse_message = prompt_registry.render("scheduler_pulse_message", project_id=project_id, reason=reason)
    pulse_context = prompt_registry.render("scheduler_pulse_context", project_id=project_id, reason=reason)
    state = {
        "project_id": project_id,
        "messages": [HumanMessage(content=pulse_message, name="system")],
        "context": pulse_context,
        "next_step": "",
        "__pulse_meta": {
            "pulse_id": pulse_id,
            "reason": reason,
            "started_at": time.time(),
        },
    }
    budget = get_inject_budget(project_id)
    text, ids = fetch_inbox_context(project_id, agent_id, budget)
    if text:
        state.setdefault("messages", [])
        state["messages"].append(SystemMessage(content=text, name="event_inbox"))
        state.setdefault("__inbox_delivered_ids", [])
        state["__inbox_delivered_ids"].extend(ids)
    new_state = agent.process(state)
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
            event = store.pick_next_event(
                project_id=project_id,
                agent_id=agent_id,
                now=now,
                cooldown_until=cooldown_until,
                preempt_types=preempt_types,
            )
            if event is None:
                if now >= float(st.cooldown_until or 0.0) and now >= float(st.backoff_until or 0.0):
                    st.run_state = AgentRunState.IDLE
                    _save_status(st)
                break

            store.mark_processing(project_id, event.event_id)
            _set_running(st, event.event_id, event.event_type)
            angelia_metrics.inc("event_picked")

            record = _to_record(event)
            handler = _resolve_handler(record.event_type)
            handler.on_pick(record)
            start = time.time()
            try:
                record_intent(intent_from_angelia_event(event, stage="processing"))
                result = handler.on_process(record)
                next_step = str(result.get("next_step", "finish"))
                if next_step == "finish":
                    empty_cycles += 1
                else:
                    empty_cycles = 0
                cooldown = _next_cooldown(project_id, next_step, empty_cycles)
                quiescent_cooldown = _finalize_quiescent_cooldown(project_id, result)
                if quiescent_cooldown > 0:
                    cooldown = max(int(cooldown), int(quiescent_cooldown))
                store.mark_done(project_id, event.event_id)
                handler.on_success(record, result)
                record_intent(intent_from_angelia_event(event, stage="done", extra_payload={"next_step": next_step}))
                _set_idle(st, cooldown)
                angelia_metrics.inc("event_done")
            except Exception as e:
                handler.on_fail(record, e)
                state = store.mark_failed_or_requeue(
                    project_id,
                    event.event_id,
                    error_code="WORKER_EXEC_ERROR",
                    error_message=str(e),
                    retry_delay_sec=min(30, max(2, 2 ** min(event.attempt + 1, 5))),
                )
                try:
                    record_intent(
                        intent_from_angelia_event(
                            event,
                            stage="failed",
                            extra_payload={"error": str(e), "queue_state": state},
                        )
                    )
                except Exception:
                    pass
                _set_error_backoff(st, str(e), delay_sec=5)
                if state == "dead":
                    handler.on_dead(record, e)
                    angelia_metrics.inc("event_dead")
                else:
                    angelia_metrics.inc("event_requeued")
            finally:
                latency_ms = int((time.time() - start) * 1000)
                if latency_ms >= 0:
                    angelia_metrics.inc("pulse_runs")

    st = _status(project_id, agent_id)
    st.run_state = AgentRunState.STOPPED
    st.current_event_id = ""
    st.current_event_type = ""
    _save_status(st)
