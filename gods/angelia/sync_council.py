"""Sync council façade backed by Athena native council engine."""
from __future__ import annotations

from gods import events as events_bus
from gods.athena import council_engine
from gods.athena.council_models import PickGateDecision


def get_state(project_id: str) -> dict:
    return council_engine.get_state(project_id)


def start_session(
    project_id: str,
    *,
    title: str,
    content: str,
    participants: list[str],
    cycles: int,
    initiator: str = "human.overseer",
    rules_profile: str = "roberts_core_v1",
    agenda: list[dict] | None = None,
    timeouts: dict | None = None,
) -> dict:
    return council_engine.start_session(
        project_id,
        title=title,
        content=content,
        participants=participants,
        cycles=cycles,
        initiator=initiator,
        rules_profile=rules_profile,
        agenda=agenda,
        timeouts=timeouts,
    )


def confirm_participant(project_id: str, agent_id: str) -> dict:
    return council_engine.confirm_participant(project_id, agent_id)


def tick(project_id: str, agent_id: str, *, has_queued: bool) -> dict:
    return council_engine.tick(project_id, agent_id, has_queued=has_queued)


def note_pulse_finished(project_id: str, agent_id: str) -> dict:
    return council_engine.note_pulse_finished(project_id, agent_id)


def evaluate_pick_gate(project_id: str, agent_id: str, event: events_bus.EventRecord | None = None) -> PickGateDecision:
    return council_engine.evaluate_pick_gate(project_id, agent_id, event=event)


def register_deferred_event(project_id: str, event_id: str) -> None:
    council_engine.register_deferred_event(project_id, event_id)


def submit_action(
    project_id: str,
    *,
    actor_id: str,
    action_type: str,
    payload: dict | None = None,
) -> dict:
    return council_engine.submit_action(project_id, actor_id=actor_id, action_type=action_type, payload=payload)


def chair_action(project_id: str, *, action: str, actor_id: str = "human.overseer") -> dict:
    return council_engine.chair_action(project_id, action=action, actor_id=actor_id)


def action_window(project_id: str, actor_id: str) -> dict:
    return council_engine.action_window(project_id, actor_id)


def list_ledger(project_id: str, *, since_seq: int = 0, limit: int = 200) -> list[dict]:
    return council_engine.list_ledger(project_id, since_seq=since_seq, limit=limit)


def list_resolutions(project_id: str, *, limit: int = 200) -> list[dict]:
    return council_engine.list_resolutions(project_id, limit=limit)
