"""Robert Rules state machine engine for synchronous council."""
from __future__ import annotations

import hashlib
import math
import time
import uuid
from typing import Any

from gods import events as events_bus
from gods.angelia.mailbox import angelia_mailbox
from gods.angelia.roberts_models import MeetingState, PickGateDecision
from gods.angelia import roberts_policy, roberts_store


PHASE_COLLECTING = "collecting"
PHASE_DRAINING = "draining"
PHASE_IN_SESSION = "in_session"
PHASE_PAUSED = "paused"
PHASE_COMPLETED = "completed"
PHASE_ABORTED = "aborted"

TURN_EVENT_TYPE = "sync_council_turn_event"


def _now() -> float:
    return float(time.time())


def _uniq(items: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in list(items or []):
        v = str(row or "").strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _default_state() -> MeetingState:
    return MeetingState()


def _append_ledger(
    project_id: str,
    state: MeetingState,
    *,
    actor_id: str,
    action_type: str,
    payload: dict[str, Any] | None = None,
    target_motion_id: str = "",
    result: str = "ok",
    error: str = "",
):
    roberts_store.append_ledger(
        project_id,
        session_id=state.session_id,
        phase=state.phase,
        actor_id=actor_id,
        action_type=action_type,
        payload=payload,
        target_motion_id=target_motion_id,
        result=result,
        error=error,
    )


def _speaker_for(state: MeetingState) -> str:
    members = _uniq(state.participants)
    if not members:
        return ""
    idx = max(0, min(int(state.current_index), len(members) - 1))
    return members[idx]


def _update_speaker(state: MeetingState) -> None:
    state.participants = _uniq(state.participants)
    state.current_speaker = _speaker_for(state)


def _active_phase(state: MeetingState) -> bool:
    return state.enabled and state.phase in {PHASE_COLLECTING, PHASE_DRAINING, PHASE_IN_SESSION, PHASE_PAUSED}


def _enqueue_turn_event(project_id: str, state: MeetingState) -> None:
    if state.phase != PHASE_IN_SESSION:
        return
    speaker = str(state.current_speaker or "").strip()
    if not speaker:
        return
    existing = events_bus.list_events(
        project_id=project_id,
        state=events_bus.EventState.QUEUED,
        agent_id=speaker,
        limit=200,
    )
    marker = f"{state.session_id}:{speaker}:{state.cycles_left}:{state.current_index}"
    for row in existing:
        if str(row.event_type or "") != TURN_EVENT_TYPE:
            continue
        if str((row.payload or {}).get("turn_marker", "") or "") == marker:
            return
    rec = events_bus.EventRecord.create(
        project_id=project_id,
        domain="angelia",
        event_type=TURN_EVENT_TYPE,
        priority=95,
        payload={
            "agent_id": speaker,
            "reason": "sync_council_turn",
            "session_id": state.session_id,
            "turn_marker": marker,
            "title": state.title,
            "content": state.content,
            "current_motion_id": state.current_motion_id,
            "current_motion": dict(state.current_motion or {}),
        },
        dedupe_key=f"sync_turn:{hashlib.sha1(marker.encode('utf-8')).hexdigest()[:16]}",
        max_attempts=3,
    )
    events_bus.append_event(rec, dedupe_window_sec=120)
    try:
        angelia_mailbox.notify(project_id, speaker)
    except Exception:
        pass


def _release_deferred(project_id: str, state: MeetingState) -> None:
    for eid in _uniq(state.deferred_event_ids):
        try:
            events_bus.set_event_meta_field(project_id, eid, "deferred_by_council", False)
            events_bus.set_event_meta_field(project_id, eid, "deferred_released_at", _now())
        except Exception:
            pass
    for aid in _uniq(state.participants):
        try:
            angelia_mailbox.notify(project_id, aid)
        except Exception:
            continue


def _advance_turn(state: MeetingState) -> None:
    members = _uniq(state.participants)
    if not members:
        state.phase = PHASE_COMPLETED
        state.enabled = False
        state.current_speaker = ""
        state.cycles_left = 0
        return
    idx = max(0, min(int(state.current_index), len(members) - 1))
    idx += 1
    if idx >= len(members):
        idx = 0
        state.cycles_left = max(0, int(state.cycles_left) - 1)
    if int(state.cycles_left) <= 0:
        state.phase = PHASE_COMPLETED
        state.enabled = False
        state.current_index = 0
        state.current_speaker = ""
        return
    state.current_index = idx
    state.current_speaker = members[idx]


def _majority(votes: dict[str, str]) -> tuple[str, dict[str, int]]:
    yes = 0
    no = 0
    abstain = 0
    for v in votes.values():
        vv = str(v or "").strip().lower()
        if vv == "yes":
            yes += 1
        elif vv == "no":
            no += 1
        else:
            abstain += 1
    decision = "pending"
    if yes > no:
        decision = "adopted"
    elif no >= yes and (yes + no) > 0:
        decision = "rejected"
    return decision, {"yes": yes, "no": no, "abstain": abstain}


def _two_thirds(votes: dict[str, str]) -> tuple[str, dict[str, int]]:
    decision, counts = _majority(votes)
    yes = counts["yes"]
    no = counts["no"]
    cast = yes + no
    if cast <= 0:
        return "pending", counts
    needed = int(math.ceil((2.0 * cast) / 3.0))
    return ("adopted" if yes >= needed else "rejected"), counts


def _evaluate_votes(state: MeetingState, action_type: str) -> tuple[str, dict[str, int]]:
    votes = dict((state.vote_state or {}).get("votes", {}) or {})
    rule = roberts_policy.required_vote_rule(action_type)
    if rule == "two_thirds":
        return _two_thirds(votes)
    return _majority(votes)


def _current_motion_or_raise(state: MeetingState) -> dict[str, Any]:
    motion = dict(state.current_motion or {})
    if not motion:
        raise ValueError("no active motion")
    return motion


def get_state(project_id: str) -> dict[str, Any]:
    return roberts_store.load_state(project_id).to_dict()


def start_session(
    project_id: str,
    *,
    title: str,
    content: str,
    participants: list[str],
    cycles: int,
    initiator: str = "human.overseer",
    rules_profile: str = roberts_policy.DEFAULT_RULES_PROFILE,
    agenda: list[dict[str, Any]] | None = None,
    timeouts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    members = _uniq(participants)
    if not members:
        raise ValueError("participants is required")
    c = max(1, int(cycles or 1))
    ag = list(agenda or [])
    if not ag:
        ag = [{"id": "agenda_1", "title": str(title or "议题"), "description": str(content or "") }]

    def _mut(_st: MeetingState):
        now = _now()
        st = _default_state()
        st.enabled = True
        st.session_id = uuid.uuid4().hex[:12]
        st.rules_profile = str(rules_profile or roberts_policy.DEFAULT_RULES_PROFILE)
        st.phase = PHASE_COLLECTING
        st.title = str(title or "").strip()
        st.content = str(content or "")
        st.agenda = ag[:1]
        st.participants = members
        st.confirmed_agents = []
        st.cycles_total = c
        st.cycles_left = c
        st.current_index = 0
        st.current_speaker = ""
        st.current_motion_id = ""
        st.motion_queue = []
        st.current_motion = {}
        st.floor_state = "open"
        st.vote_state = {"rule": "simple_majority", "votes": {}, "target_motion_id": ""}
        st.deferred_event_ids = []
        st.resolution_ids = []
        st.created_at = now
        st.updated_at = now
        st.last_transition_at = now
        st.last_transition_reason = "session_started"
        st.initiator = str(initiator or "human.overseer")
        result = st.to_dict()
        result["timeouts"] = roberts_policy.normalize_timeouts(timeouts)
        return st, result

    st, result = roberts_store.with_state_lock(project_id, _mut)
    _append_ledger(project_id, st, actor_id=initiator, action_type="session_start", payload=result)
    return result


def confirm_participant(project_id: str, agent_id: str) -> dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        raise ValueError("agent_id is required")

    def _mut(st: MeetingState):
        if not st.enabled:
            raise ValueError("sync council is not enabled")
        if aid not in set(_uniq(st.participants)):
            raise ValueError(f"agent '{aid}' is not in participants")
        confirmed = _uniq(st.confirmed_agents)
        if aid not in confirmed:
            confirmed.append(aid)
        st.confirmed_agents = confirmed
        if set(confirmed) >= set(_uniq(st.participants)):
            st.phase = PHASE_DRAINING
            st.last_transition_reason = "all_confirmed"
            st.last_transition_at = _now()
        return st, {
            "participants_confirmed": len(st.confirmed_agents),
            "participants_total": len(st.participants),
            "phase": st.phase,
            "session_ready": bool(st.phase == PHASE_DRAINING),
        }

    st, result = roberts_store.with_state_lock(project_id, _mut)
    _append_ledger(project_id, st, actor_id=aid, action_type="confirm_participant", payload=result)
    payload = st.to_dict()
    payload.update(result)
    return payload


def _transition_if_ready(project_id: str, st: MeetingState, *, has_queued: bool) -> MeetingState:
    if not st.enabled:
        return st
    if st.phase == PHASE_DRAINING:
        # Transition to in_session when no participant is running.
        raw = {}
        try:
            import json
            from gods.paths import runtime_dir

            p = runtime_dir(project_id) / "angelia_agents.json"
            if p.exists():
                raw = json.loads(p.read_text(encoding="utf-8")) if p.read_text(encoding="utf-8").strip() else {}
        except Exception:
            raw = {}
        running = False
        for aid in _uniq(st.participants):
            row = raw.get(aid, {}) if isinstance(raw, dict) else {}
            if isinstance(row, dict) and str(row.get("run_state", "")).strip().lower() == "running":
                running = True
                break
        if not running:
            st.phase = PHASE_IN_SESSION
            st.current_index = 0
            st.cycles_left = max(1, int(st.cycles_left or st.cycles_total or 1))
            _update_speaker(st)
            st.last_transition_reason = "draining_complete"
            st.last_transition_at = _now()
            _enqueue_turn_event(project_id, st)
        return st
    if st.phase == PHASE_IN_SESSION:
        if not has_queued:
            # avoid dead turn when speaker has no queued work
            _advance_turn(st)
            st.last_transition_reason = "speaker_idle_no_event"
            st.last_transition_at = _now()
            if st.phase == PHASE_COMPLETED:
                _release_deferred(project_id, st)
            else:
                _enqueue_turn_event(project_id, st)
        return st
    return st


def tick(project_id: str, agent_id: str, *, has_queued: bool) -> dict[str, Any]:
    def _mut(st: MeetingState):
        st = _transition_if_ready(project_id, st, has_queued=bool(has_queued))
        return st, st.to_dict()

    st, result = roberts_store.with_state_lock(project_id, _mut)
    return result


def note_pulse_finished(project_id: str, agent_id: str) -> dict[str, Any]:
    aid = str(agent_id or "").strip()

    def _mut(st: MeetingState):
        if not st.enabled or st.phase != PHASE_IN_SESSION:
            return st, st.to_dict()
        if aid and aid == str(st.current_speaker or ""):
            _advance_turn(st)
            st.last_transition_reason = "speaker_pulse_finished"
            st.last_transition_at = _now()
            if st.phase == PHASE_COMPLETED:
                _release_deferred(project_id, st)
            else:
                _enqueue_turn_event(project_id, st)
        return st, st.to_dict()

    st, result = roberts_store.with_state_lock(project_id, _mut)
    return result


def register_deferred_event(project_id: str, event_id: str) -> None:
    eid = str(event_id or "").strip()
    if not eid:
        return

    def _mut(st: MeetingState):
        if not _active_phase(st):
            return st, None
        cur = _uniq(st.deferred_event_ids)
        if eid not in cur:
            cur.append(eid)
        st.deferred_event_ids = cur[-5000:]
        return st, None

    roberts_store.with_state_lock(project_id, _mut)
    try:
        events_bus.set_event_meta_field(project_id, eid, "deferred_by_council", True)
    except Exception:
        pass


def evaluate_pick_gate(project_id: str, agent_id: str, event: events_bus.EventRecord | None = None) -> PickGateDecision:
    aid = str(agent_id or "").strip()
    state = MeetingState.from_dict(tick(project_id, aid, has_queued=True))
    if not state.enabled:
        return PickGateDecision(True, "council_disabled", False)
    members = set(_uniq(state.participants))
    if aid not in members:
        return PickGateDecision(True, "non_participant", False)
    if state.phase in {PHASE_COLLECTING, PHASE_DRAINING, PHASE_PAUSED}:
        return PickGateDecision(False, f"{state.phase}_blocked", True)
    if state.phase != PHASE_IN_SESSION:
        return PickGateDecision(False, f"phase:{state.phase}", True)
    if str(state.current_speaker or "") != aid:
        return PickGateDecision(False, f"waiting_turn:{state.current_speaker}", True)

    # Only council-turn events are considered council-related queue input.
    if event is not None and str(getattr(event, "event_type", "") or "") != TURN_EVENT_TYPE:
        return PickGateDecision(False, "defer_non_council_event", True)
    return PickGateDecision(True, "speaker_turn", False)


def _allowed_actions(state: MeetingState, actor_id: str) -> list[str]:
    out: list[str] = []
    actor = str(actor_id or "").strip()
    if actor == "human.overseer":
        out.extend(["chair.pause", "chair.resume", "chair.terminate", "chair.skip_turn"])
    if state.phase != PHASE_IN_SESSION:
        return sorted(set(out))
    if actor not in set(_uniq(state.participants)):
        return sorted(set(out))
    motion = dict(state.current_motion or {})
    mstate = str(motion.get("state", "") or "")
    if not motion:
        out.append("motion_submit")
    else:
        if mstate == "proposed":
            if actor != str(motion.get("proposer", "") or ""):
                out.append("motion_second")
            out.append("procedural_table_motion")
        if mstate in {"seconded", "debating", "amendment_pending"}:
            if actor == str(state.current_speaker or ""):
                out.extend(["debate_speak", "amend_submit", "procedural_call_question", "procedural_table_motion"])
            if mstate == "amendment_pending" and actor != str(motion.get("pending_amendment", {}).get("proposer", "") or ""):
                out.append("amend_second")
        if mstate == "voting":
            out.append("vote_cast")
    return sorted(set(out))


def _new_motion(actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", "") or payload.get("content", "")).strip()
    if not text:
        raise ValueError("motion text is required")
    mid = "motion_" + uuid.uuid4().hex[:10]
    return {
        "motion_id": mid,
        "title": str(payload.get("title", "动议") or "动议"),
        "text": text,
        "state": "proposed",
        "proposer": actor_id,
        "seconded_by": "",
        "debate": [],
        "pending_amendment": {},
        "votes": {},
        "created_at": _now(),
        "updated_at": _now(),
    }


def _write_resolution(project_id: str, state: MeetingState, motion: dict[str, Any], counts: dict[str, int]) -> dict[str, Any]:
    rid = "res_" + uuid.uuid4().hex[:10]
    resolution = {
        "resolution_id": rid,
        "session_id": state.session_id,
        "motion_id": str(motion.get("motion_id", "")),
        "decision": str(motion.get("state", "")),
        "votes": counts,
        "obligations": {
            "summary": str(motion.get("text", ""))[:500],
            "participants": list(state.participants or []),
        },
        "execution_tasks": [
            {
                "task_id": f"task_{uuid.uuid4().hex[:8]}",
                "title": str(motion.get("title", "动议执行")),
                "description": str(motion.get("text", "")),
                "assignees": list(state.participants or []),
                "status": "draft",
            }
        ],
        "hermes_contract_draft": {
            "title": f"SyncCouncil::{state.title or '议题'}",
            "version": "0.1.0-draft",
            "description": str(motion.get("text", "")),
            "submitter": "human.overseer",
            "committers": list(state.participants or []),
            "status": "draft",
            "default_obligations": [],
            "obligations": {},
        },
        "created_at": _now(),
    }
    roberts_store.append_resolution(project_id, resolution)
    try:
        import json
        from gods.mnemosyne import facade as mnemosyne_facade

        md = (
            f"# Sync Council Resolution\\n\\n"
            f"- session_id: {state.session_id}\\n"
            f"- resolution_id: {rid}\\n"
            f"- motion_id: {motion.get('motion_id', '')}\\n"
            f"- decision: {motion.get('state', '')}\\n"
            f"- votes: yes={counts.get('yes', 0)} no={counts.get('no', 0)} abstain={counts.get('abstain', 0)}\\n\\n"
            f"## Motion\\n{motion.get('text', '')}\\n\\n"
            f"## Execution Tasks\\n```json\\n{json.dumps(resolution['execution_tasks'], ensure_ascii=False, indent=2)}\\n```\\n"
        )
        mnemosyne_facade.write_entry(
            project_id=project_id,
            vault="human",
            author="system.sync_council",
            title=f"SyncCouncil Resolution {rid}",
            content=md,
            tags=["sync_council", "resolution", str(motion.get("state", ""))],
        )
    except Exception:
        pass
    return resolution


def submit_action(
    project_id: str,
    *,
    actor_id: str,
    action_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actor = str(actor_id or "").strip()
    action = str(action_type or "").strip()
    pl = dict(payload or {})
    if not actor:
        raise ValueError("actor_id is required")
    if not action:
        raise ValueError("action_type is required")

    def _mut(st: MeetingState):
        if not st.enabled:
            raise ValueError("sync council is not enabled")
        if st.phase != PHASE_IN_SESSION:
            raise ValueError(f"sync council phase '{st.phase}' does not accept actions")
        if actor not in set(_uniq(st.participants)) and actor != "human.overseer":
            raise ValueError("actor is not participant")
        allowed = set(_allowed_actions(st, actor))
        if action not in allowed:
            raise ValueError(f"action '{action}' is not allowed now")

        motion = dict(st.current_motion or {})
        target_motion_id = str(motion.get("motion_id", "") or "")

        if action == "motion_submit":
            motion = _new_motion(actor, pl)
            st.current_motion = motion
            st.current_motion_id = str(motion.get("motion_id", ""))
            st.floor_state = "motion_open"
            st.vote_state = {"rule": "simple_majority", "votes": {}, "target_motion_id": st.current_motion_id}

        elif action == "motion_second":
            motion = _current_motion_or_raise(st)
            if str(motion.get("state", "")) != "proposed":
                raise ValueError("motion is not in proposed state")
            motion["state"] = "debating"
            motion["seconded_by"] = actor
            motion["updated_at"] = _now()
            st.current_motion = motion

        elif action == "debate_speak":
            motion = _current_motion_or_raise(st)
            if str(motion.get("state", "")) not in {"debating", "amendment_pending"}:
                raise ValueError("motion is not in debating state")
            speech = str(pl.get("speech", "") or pl.get("text", "")).strip()
            if not speech:
                raise ValueError("speech is required")
            debate = list(motion.get("debate", []) or [])
            debate.append({"speaker": actor, "speech": speech, "ts": _now()})
            motion["debate"] = debate[-200:]
            motion["updated_at"] = _now()
            st.current_motion = motion

        elif action == "amend_submit":
            motion = _current_motion_or_raise(st)
            if str(motion.get("state", "")) not in {"debating", "seconded"}:
                raise ValueError("motion cannot be amended now")
            amend = str(pl.get("text", "") or pl.get("amendment", "")).strip()
            if not amend:
                raise ValueError("amendment text is required")
            motion["state"] = "amendment_pending"
            motion["pending_amendment"] = {
                "proposer": actor,
                "text": amend,
                "state": "proposed",
                "ts": _now(),
            }
            motion["updated_at"] = _now()
            st.current_motion = motion

        elif action == "amend_second":
            motion = _current_motion_or_raise(st)
            pending = dict(motion.get("pending_amendment", {}) or {})
            if not pending:
                raise ValueError("no pending amendment")
            if actor == str(pending.get("proposer", "") or ""):
                raise ValueError("amend proposer cannot second")
            motion["text"] = str(motion.get("text", "") or "") + "\n[AMENDMENT] " + str(pending.get("text", ""))
            motion["state"] = "debating"
            motion["pending_amendment"] = {}
            motion["updated_at"] = _now()
            st.current_motion = motion

        elif action == "procedural_call_question":
            motion = _current_motion_or_raise(st)
            if str(motion.get("state", "")) not in {"debating", "amendment_pending", "seconded"}:
                raise ValueError("motion cannot enter voting now")
            motion["state"] = "voting"
            motion["updated_at"] = _now()
            st.current_motion = motion
            st.vote_state = {"rule": "simple_majority", "votes": {}, "target_motion_id": str(motion.get("motion_id", ""))}

        elif action == "procedural_table_motion":
            motion = _current_motion_or_raise(st)
            motion["state"] = "tabled"
            motion["updated_at"] = _now()
            st.current_motion = motion
            st.current_motion_id = ""
            st.current_motion = {}
            st.vote_state = {"rule": "simple_majority", "votes": {}, "target_motion_id": ""}

        elif action == "vote_cast":
            motion = _current_motion_or_raise(st)
            if str(motion.get("state", "")) != "voting":
                raise ValueError("motion is not in voting state")
            choice = str(pl.get("choice", "") or "").strip().lower()
            if choice not in {"yes", "no", "abstain"}:
                raise ValueError("choice must be yes|no|abstain")
            votes = dict((st.vote_state or {}).get("votes", {}) or {})
            votes[actor] = choice
            st.vote_state = {"rule": "simple_majority", "votes": votes, "target_motion_id": str(motion.get("motion_id", ""))}
            decision, counts = _evaluate_votes(st, action)
            total = len(_uniq(st.participants))
            if len(votes) >= total:
                motion["state"] = decision
                motion["votes"] = votes
                motion["updated_at"] = _now()
                st.current_motion = motion
                if decision == "adopted":
                    res = _write_resolution(project_id, st, motion, counts)
                    st.resolution_ids = _uniq(list(st.resolution_ids or []) + [str(res.get("resolution_id", ""))])
                st.current_motion_id = ""
                st.current_motion = {}
                st.vote_state = {"rule": "simple_majority", "votes": {}, "target_motion_id": ""}

        elif action == "reconsider_submit":
            target = str(pl.get("resolution_id", "") or "").strip()
            if not target:
                raise ValueError("resolution_id is required")
            motion = _new_motion(actor, {"title": "复议", "text": f"Reconsider {target}"})
            st.current_motion = motion
            st.current_motion_id = str(motion.get("motion_id", ""))

        elif action == "reconsider_second":
            motion = _current_motion_or_raise(st)
            if str(motion.get("title", "")) != "复议":
                raise ValueError("current motion is not reconsider")
            motion["state"] = "debating"
            motion["seconded_by"] = actor
            motion["updated_at"] = _now()
            st.current_motion = motion

        else:
            raise ValueError(f"unsupported action_type: {action}")

        st.last_transition_at = _now()
        st.last_transition_reason = f"action:{action}"
        return st, {
            "ok": True,
            "phase": st.phase,
            "current_motion": dict(st.current_motion or {}),
            "vote_state": dict(st.vote_state or {}),
            "allowed_actions": _allowed_actions(st, actor),
        }

    try:
        st, result = roberts_store.with_state_lock(project_id, _mut)
        _append_ledger(
            project_id,
            st,
            actor_id=actor,
            action_type=action,
            payload=pl,
            target_motion_id=str((st.current_motion or {}).get("motion_id", "") or ""),
        )
        out = st.to_dict()
        out["action_result"] = result
        out["allowed_actions"] = _allowed_actions(st, actor)
        return out
    except Exception as e:
        st = roberts_store.load_state(project_id)
        _append_ledger(
            project_id,
            st,
            actor_id=actor,
            action_type=action,
            payload=pl,
            result="error",
            error=str(e),
        )
        raise


def chair_action(project_id: str, *, action: str, actor_id: str = "human.overseer") -> dict[str, Any]:
    act = str(action or "").strip().lower()
    if act not in roberts_policy.CHAIR_ACTIONS:
        raise ValueError("unsupported chair action")

    def _mut(st: MeetingState):
        if not st.enabled and act != "resume":
            raise ValueError("sync council is not enabled")
        if act == "pause":
            st.phase = PHASE_PAUSED
            st.last_transition_reason = "chair_pause"
        elif act == "resume":
            if st.phase == PHASE_PAUSED:
                st.phase = PHASE_IN_SESSION
                _update_speaker(st)
                _enqueue_turn_event(project_id, st)
            st.enabled = True
            st.last_transition_reason = "chair_resume"
        elif act == "terminate":
            st.phase = PHASE_ABORTED
            st.enabled = False
            st.current_speaker = ""
            st.current_index = 0
            st.last_transition_reason = "chair_terminate"
            _release_deferred(project_id, st)
        elif act == "skip_turn":
            if st.phase != PHASE_IN_SESSION:
                raise ValueError("skip_turn only available in_session")
            _advance_turn(st)
            st.last_transition_reason = "chair_skip_turn"
            if st.phase == PHASE_COMPLETED:
                _release_deferred(project_id, st)
            else:
                _enqueue_turn_event(project_id, st)
        st.last_transition_at = _now()
        return st, st.to_dict()

    st, result = roberts_store.with_state_lock(project_id, _mut)
    _append_ledger(
        project_id,
        st,
        actor_id=actor_id,
        action_type=roberts_policy.CHAIR_ACTIONS[act],
        payload={"action": act},
    )
    return result


def action_window(project_id: str, actor_id: str) -> dict[str, Any]:
    st = roberts_store.load_state(project_id)
    return {
        "phase": st.phase,
        "actor_id": actor_id,
        "current_speaker": st.current_speaker,
        "allowed_actions": _allowed_actions(st, actor_id),
    }


def list_ledger(project_id: str, *, since_seq: int = 0, limit: int = 200) -> list[dict[str, Any]]:
    return roberts_store.list_ledger(project_id, since_seq=since_seq, limit=limit)


def list_resolutions(project_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
    return roberts_store.list_resolutions(project_id, limit=limit)
