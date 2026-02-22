"""Council tools for autonomous Robert-rules meeting participation."""
from __future__ import annotations

import json

from langchain_core.tools import tool

from gods.angelia import sync_council


def _fmt_error(title: str, detail: str, hint: str = "") -> str:
    lines = [f"[{title}]", str(detail or "")]
    if hint:
        lines.append(f"Hint: {hint}")
    return "\n".join(lines)


@tool
def council_status(caller_id: str, project_id: str = "default") -> str:
    """Inspect current sync-council meeting status and actions available to caller."""
    try:
        state = dict(sync_council.get_state(project_id) or {})
        window = dict(sync_council.action_window(project_id, caller_id) or {})
        phase = str(state.get("phase", "none") or "none")
        enabled = bool(state.get("enabled", False))
        speaker = str(state.get("current_speaker", "") or "-")
        title = str(state.get("title", "") or "")
        allowed = list(window.get("allowed_actions", []) or [])
        return (
            f"[COUNCIL_STATUS] enabled={enabled} phase={phase} speaker={speaker}\n"
            f"title={title}\n"
            f"allowed_actions={','.join(allowed) if allowed else '(none)'}"
        )
    except Exception as e:
        return _fmt_error("COUNCIL_STATUS_ERROR", str(e), "Verify sync council is started for current project.")


@tool
def council_confirm(caller_id: str, project_id: str = "default") -> str:
    """Confirm caller's participation in current sync-council session."""
    try:
        st = dict(sync_council.confirm_participant(project_id, caller_id) or {})
        return (
            f"[COUNCIL_CONFIRM] agent={caller_id} phase={st.get('phase', '')} "
            f"confirmed={len(list(st.get('confirmed_agents', []) or []))}/"
            f"{len(list(st.get('participants', []) or []))}"
        )
    except Exception as e:
        return _fmt_error("COUNCIL_CONFIRM_ERROR", str(e), "Ensure caller is in participants and session is enabled.")


@tool
def council_action(
    action_type: str,
    payload_json: str,
    caller_id: str,
    project_id: str = "default",
) -> str:
    """Submit one Robert-rules action (motion/debate/amend/procedural/vote/reconsider)."""
    try:
        payload = json.loads(str(payload_json or "{}"))
        if not isinstance(payload, dict):
            return _fmt_error("COUNCIL_ACTION_ERROR", "payload_json must decode to object", "Use '{}' or '{\"text\":\"...\"}'.")
    except Exception as e:
        return _fmt_error("COUNCIL_ACTION_ERROR", f"invalid payload_json: {e}", "Use valid JSON object string.")

    try:
        st = dict(
            sync_council.submit_action(
                project_id,
                actor_id=caller_id,
                action_type=str(action_type or "").strip(),
                payload=payload,
            )
            or {}
        )
        ar = dict(st.get("action_result", {}) or {})
        phase = str(st.get("phase", "") or "")
        cur = dict(st.get("current_motion", {}) or {})
        return (
            f"[COUNCIL_ACTION] action={action_type} phase={phase} ok={bool(ar.get('ok', True))}\n"
            f"current_motion_id={cur.get('motion_id', '')} state={cur.get('state', '')}\n"
            f"allowed_actions={','.join(list(st.get('allowed_actions', []) or []))}"
        )
    except Exception as e:
        return _fmt_error("COUNCIL_ACTION_ERROR", str(e), "Call council_status first and only use allowed_actions.")


@tool
def council_ledger(since_seq: int, limit: int, caller_id: str, project_id: str = "default") -> str:
    """Read sync-council action ledger for replay/debug."""
    try:
        rows = list(sync_council.list_ledger(project_id, since_seq=max(0, int(since_seq or 0)), limit=max(1, min(int(limit or 30), 200))) or [])
        if not rows:
            return "[COUNCIL_LEDGER] (empty)"
        lines = [f"[COUNCIL_LEDGER] rows={len(rows)}"]
        for r in rows:
            lines.append(
                f"- seq={r.get('seq')} phase={r.get('phase')} actor={r.get('actor_id')} "
                f"action={r.get('action_type')} result={r.get('result')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return _fmt_error("COUNCIL_LEDGER_ERROR", str(e), "Check project_id and council session state.")


@tool
def council_resolutions(limit: int, caller_id: str, project_id: str = "default") -> str:
    """Read latest sync-council resolutions and execution drafts."""
    try:
        rows = list(sync_council.list_resolutions(project_id, limit=max(1, min(int(limit or 20), 200))) or [])
        if not rows:
            return "[COUNCIL_RESOLUTIONS] (empty)"
        lines = [f"[COUNCIL_RESOLUTIONS] rows={len(rows)}"]
        for r in rows:
            lines.append(
                f"- resolution_id={r.get('resolution_id')} decision={r.get('decision')} "
                f"motion_id={r.get('motion_id')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return _fmt_error("COUNCIL_RESOLUTIONS_ERROR", str(e), "Check project_id and council history.")
