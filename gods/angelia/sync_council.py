"""Synchronous council orchestration on top of Angelia async runtime.

Phase model:
- collecting: waiting participant confirmations
- draining:   all confirmed; block new picks for participant group until no one is running
- round_robin:only current speaker can pick events
- done:       session finished
"""
from __future__ import annotations

import fcntl
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gods.paths import runtime_dir, runtime_locks_dir


_PHASE_COLLECTING = "collecting"
_PHASE_DRAINING = "draining"
_PHASE_ROUND_ROBIN = "round_robin"
_PHASE_DONE = "done"


@dataclass(frozen=True)
class PickGateDecision:
    allowed: bool
    reason: str


def _state_path(project_id: str) -> Path:
    p = runtime_dir(project_id) / "sync_council.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _lock_path(project_id: str) -> Path:
    p = runtime_locks_dir(project_id) / "sync_council.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _normalize_agents(items: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in list(items or []):
        aid = str(row or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        out.append(aid)
    return out


def _default_state() -> dict[str, Any]:
    return {
        "enabled": False,
        "phase": _PHASE_DONE,
        "title": "",
        "content": "",
        "participants": [],
        "confirmed_agents": [],
        "cycles_total": 0,
        "cycles_left": 0,
        "current_index": 0,
        "current_speaker": "",
        "created_at": 0.0,
        "updated_at": 0.0,
        "last_transition_at": 0.0,
    }


def _load_state(project_id: str) -> dict[str, Any]:
    p = _state_path(project_id)
    if not p.exists():
        return _default_state()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            out = _default_state()
            out.update(data)
            out["participants"] = _normalize_agents(out.get("participants", []))
            out["confirmed_agents"] = _normalize_agents(out.get("confirmed_agents", []))
            return out
    except Exception:
        pass
    return _default_state()


def _save_state(project_id: str, state: dict[str, Any]) -> None:
    p = _state_path(project_id)
    payload = dict(_default_state())
    payload.update(dict(state or {}))
    payload["participants"] = _normalize_agents(payload.get("participants", []))
    payload["confirmed_agents"] = _normalize_agents(payload.get("confirmed_agents", []))
    payload["updated_at"] = float(time.time())
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _with_state_lock(project_id: str, mutator):
    lp = _lock_path(project_id)
    lp.touch(exist_ok=True)
    with lp.open("r+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            state = _load_state(project_id)
            new_state, result = mutator(state)
            _save_state(project_id, new_state)
            return result
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _read_agent_runtime_states(project_id: str) -> dict[str, str]:
    p = runtime_dir(project_id) / "angelia_agents.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for aid, row in raw.items():
        if not isinstance(row, dict):
            continue
        out[str(aid)] = str(row.get("run_state", "") or "").strip().lower()
    return out


def _all_participants_not_running(project_id: str, participants: list[str]) -> bool:
    states = _read_agent_runtime_states(project_id)
    for aid in list(participants or []):
        if states.get(aid, "") == "running":
            return False
    return True


def _set_round_robin(state: dict[str, Any]) -> dict[str, Any]:
    participants = _normalize_agents(state.get("participants", []))
    cycles_total = int(state.get("cycles_total", 0) or 0)
    cycles_total = max(1, cycles_total)
    state["participants"] = participants
    state["phase"] = _PHASE_ROUND_ROBIN
    state["cycles_total"] = cycles_total
    state["cycles_left"] = int(state.get("cycles_left", 0) or cycles_total) or cycles_total
    state["current_index"] = 0
    state["current_speaker"] = participants[0] if participants else ""
    state["last_transition_at"] = float(time.time())
    return state


def _advance_turn(state: dict[str, Any], *, reason: str = "") -> dict[str, Any]:
    participants = _normalize_agents(state.get("participants", []))
    if not participants:
        state["enabled"] = False
        state["phase"] = _PHASE_DONE
        state["current_speaker"] = ""
        state["current_index"] = 0
        state["cycles_left"] = 0
        state["last_transition_at"] = float(time.time())
        return state

    idx = int(state.get("current_index", 0) or 0)
    idx = max(0, min(idx, len(participants) - 1))
    next_idx = idx + 1
    cycles_left = int(state.get("cycles_left", state.get("cycles_total", 1)) or 1)
    if next_idx >= len(participants):
        next_idx = 0
        cycles_left -= 1
    if cycles_left <= 0:
        state["enabled"] = False
        state["phase"] = _PHASE_DONE
        state["current_speaker"] = ""
        state["current_index"] = 0
        state["cycles_left"] = 0
        state["last_transition_at"] = float(time.time())
        if reason:
            state["last_transition_reason"] = str(reason)
        return state
    state["phase"] = _PHASE_ROUND_ROBIN
    state["current_index"] = int(next_idx)
    state["current_speaker"] = participants[next_idx]
    state["cycles_left"] = int(cycles_left)
    state["last_transition_at"] = float(time.time())
    if reason:
        state["last_transition_reason"] = str(reason)
    return state


def get_state(project_id: str) -> dict[str, Any]:
    return _load_state(project_id)


def start_session(
    project_id: str,
    *,
    title: str,
    content: str,
    participants: list[str],
    cycles: int,
    initiator: str = "human.overseer",
) -> dict[str, Any]:
    members = _normalize_agents(participants)
    if not members:
        raise ValueError("participants is required")
    c = max(1, int(cycles or 1))

    def _mut(state: dict[str, Any]):
        now = float(time.time())
        next_state = dict(state)
        next_state.update(
            {
                "enabled": True,
                "phase": _PHASE_COLLECTING,
                "title": str(title or "").strip(),
                "content": str(content or ""),
                "participants": members,
                "confirmed_agents": [],
                "cycles_total": c,
                "cycles_left": c,
                "current_index": 0,
                "current_speaker": "",
                "created_at": now,
                "updated_at": now,
                "last_transition_at": now,
                "initiator": str(initiator or "human.overseer"),
                "last_transition_reason": "session_started",
            }
        )
        return next_state, dict(next_state)

    return _with_state_lock(project_id, _mut)


def confirm_participant(project_id: str, agent_id: str) -> dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        raise ValueError("agent_id is required")

    def _mut(state: dict[str, Any]):
        next_state = dict(state)
        if not bool(next_state.get("enabled", False)):
            raise ValueError("sync council is not enabled")
        participants = _normalize_agents(next_state.get("participants", []))
        if aid not in participants:
            raise ValueError(f"agent '{aid}' is not in participants")
        confirmed = _normalize_agents(next_state.get("confirmed_agents", []))
        if aid not in confirmed:
            confirmed.append(aid)
        next_state["confirmed_agents"] = confirmed
        if set(confirmed) >= set(participants):
            next_state["phase"] = _PHASE_DRAINING
            next_state["last_transition_at"] = float(time.time())
            next_state["last_transition_reason"] = "all_confirmed"
        return next_state, dict(next_state)

    return _with_state_lock(project_id, _mut)


def tick(project_id: str, agent_id: str, *, has_queued: bool) -> dict[str, Any]:
    """Progress draining->round_robin and speaker rotation when idle with no queued events."""

    aid = str(agent_id or "").strip()

    def _mut(state: dict[str, Any]):
        next_state = dict(state)
        if not bool(next_state.get("enabled", False)):
            return next_state, dict(next_state)
        phase = str(next_state.get("phase", _PHASE_DONE))
        participants = _normalize_agents(next_state.get("participants", []))
        if phase == _PHASE_DRAINING:
            if _all_participants_not_running(project_id, participants):
                next_state = _set_round_robin(next_state)
                next_state["last_transition_reason"] = "draining_complete"
            return next_state, dict(next_state)
        if phase == _PHASE_ROUND_ROBIN:
            current = str(next_state.get("current_speaker", "") or "")
            if aid and aid == current and not bool(has_queued):
                # No queued work for current speaker -> advance to avoid dead turn.
                next_state = _advance_turn(next_state, reason="speaker_idle_no_event")
            return next_state, dict(next_state)
        return next_state, dict(next_state)

    return _with_state_lock(project_id, _mut)


def note_pulse_finished(project_id: str, agent_id: str) -> dict[str, Any]:
    aid = str(agent_id or "").strip()

    def _mut(state: dict[str, Any]):
        next_state = dict(state)
        if not bool(next_state.get("enabled", False)):
            return next_state, dict(next_state)
        if str(next_state.get("phase", "")) != _PHASE_ROUND_ROBIN:
            return next_state, dict(next_state)
        current = str(next_state.get("current_speaker", "") or "")
        if aid and current and aid == current:
            next_state = _advance_turn(next_state, reason="speaker_pulse_finished")
        return next_state, dict(next_state)

    return _with_state_lock(project_id, _mut)


def evaluate_pick_gate(project_id: str, agent_id: str) -> PickGateDecision:
    aid = str(agent_id or "").strip()
    state = tick(project_id, aid, has_queued=True)
    if not bool(state.get("enabled", False)):
        return PickGateDecision(True, "council_disabled")
    participants = set(_normalize_agents(state.get("participants", [])))
    if aid not in participants:
        return PickGateDecision(True, "non_participant")
    phase = str(state.get("phase", _PHASE_DONE))
    if phase in {_PHASE_COLLECTING, _PHASE_DRAINING}:
        return PickGateDecision(False, f"{phase}_blocked")
    if phase == _PHASE_ROUND_ROBIN:
        speaker = str(state.get("current_speaker", "") or "")
        if speaker and aid != speaker:
            return PickGateDecision(False, f"waiting_turn:{speaker}")
        return PickGateDecision(True, "speaker_turn")
    return PickGateDecision(False, f"phase:{phase}")

