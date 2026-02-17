"""Human/social communication tools."""
from __future__ import annotations

import fcntl
import json
import time

from langchain_core.tools import tool

from gods.iris import enqueue_message
from gods.paths import mnemosyne_dir, project_buffers_dir, project_dir
from gods.angelia.pulse import get_priority_weights, is_inbox_event_enabled
from gods.tools.comm_common import format_comm_error


@tool
def send_message(to_id: str, title: str, message: str, caller_id: str, project_id: str = "default") -> str:
    """Send a private revelation to another Being within the same project."""
    try:
        if not to_id.strip():
            return format_comm_error(
                "Message Error",
                "Target agent id is empty.",
                "Set to_id to a valid agent id, e.g. 'sheep' or 'ground'.",
                caller_id,
                project_id,
            )
        if not title.strip():
            return format_comm_error(
                "Message Error",
                "Message title is empty.",
                "Provide a concise title before sending, e.g. 'Commit Done'.",
                caller_id,
                project_id,
            )
        if not message.strip():
            return format_comm_error(
                "Message Error",
                "Message content is empty.",
                "Provide a concrete message payload before sending.",
                caller_id,
                project_id,
            )

        weights = get_priority_weights(project_id)
        trigger = is_inbox_event_enabled(project_id)
        queued = enqueue_message(
            project_id=project_id,
            agent_id=to_id,
            sender=caller_id,
            title=title,
            content=message,
            msg_type="private",
            trigger_pulse=trigger,
            pulse_priority=int(weights.get("inbox_event", 100)),
        )
        return (
            f"Revelation sent to {to_id}. "
            f"title={title}, "
            f"event_id={queued.get('inbox_event_id', '')}, "
            f"outbox_receipt_id={queued.get('outbox_receipt_id', '')}, "
            f"outbox_status={queued.get('outbox_status', 'pending')}, "
            f"pulse_triggered={str(bool(trigger)).lower()}, "
            "initial_state=pending"
        )
    except Exception as e:
        return format_comm_error(
            "Communication Error",
            str(e),
            "Retry send_message and verify project buffers are writable.",
            caller_id,
            project_id,
        )


@tool
def send_to_human(message: str, caller_id: str, project_id: str = "default") -> str:
    """Sacred prayer sent to the human overseer."""
    try:
        if not message.strip():
            return format_comm_error(
                "Message Error",
                "Prayer message is empty.",
                "Provide what you need to report or request from human.",
                caller_id,
                project_id,
            )

        buffer_dir = project_buffers_dir(project_id)
        buffer_dir.mkdir(parents=True, exist_ok=True)
        target_buffer = buffer_dir / "human.jsonl"
        msg_data = {"timestamp": time.time(), "from": caller_id, "type": "prayer", "content": message}

        with open(target_buffer, "a", encoding="utf-8") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps(msg_data, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return "Prayer sent to the High Overseer (Human)."
    except Exception as e:
        return format_comm_error(
            "Communication Error",
            str(e),
            "Retry send_to_human and verify project buffers are writable.",
            caller_id,
            project_id,
        )


@tool
def finalize(
    mode: str = "done",
    sleep_sec: int = 0,
    reason: str = "",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """Signal pulse finalization. mode=done|quiescent; quiescent requests bounded sleep cooldown."""
    try:
        from gods.config import runtime_config

        proj = runtime_config.projects.get(project_id)
        enabled = bool(getattr(proj, "finalize_quiescent_enabled", True) if proj else True)
        min_sec = int(getattr(proj, "finalize_sleep_min_sec", 15) if proj else 15)
        default_sec = int(getattr(proj, "finalize_sleep_default_sec", 120) if proj else 120)
        max_sec = int(getattr(proj, "finalize_sleep_max_sec", 1800) if proj else 1800)
        min_sec = max(5, min(min_sec, 3600))
        max_sec = max(min_sec, min(max_sec, 24 * 3600))
        default_sec = max(min_sec, min(default_sec, max_sec))

        md = str(mode or "done").strip().lower()
        if md not in {"done", "quiescent"}:
            md = "done"
        if md == "quiescent" and not enabled:
            md = "done"

        req = int(sleep_sec or 0)
        if req <= 0:
            applied = default_sec
        else:
            applied = max(min_sec, min(req, max_sec))
        if md == "done":
            applied = 0

        return json.dumps(
            {
                "ok": True,
                "finalize": {
                    "mode": md,
                    "requested_sleep_sec": int(req),
                    "applied_sleep_sec": int(applied),
                    "min_sleep_sec": int(min_sec),
                    "default_sleep_sec": int(default_sec),
                    "max_sleep_sec": int(max_sec),
                    "quiescent_enabled": bool(enabled),
                    "reason": str(reason or ""),
                },
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool
def post_to_synod(reason: str, message: str, caller_id: str = "default") -> str:
    """Escalate to public Synod discussion."""
    return f"[[SYNOD_RESONANCE]] Requesting public discussion for: {reason}. Content: {message}"


@tool
def abstain_from_synod(reason: str, caller_id: str = "default") -> str:
    """Abstain from current public discussion."""
    return f"[[ABSTAIN]] Reason: {reason}"


@tool
def list_agents(caller_id: str, project_id: str = "default") -> str:
    """List all agents in current project with short role summary from Mnemosyne profiles."""
    try:
        agents_root = project_dir(project_id) / "agents"
        if not agents_root.exists():
            return "No agents found in this project."

        results = []
        for agent_dir in sorted([p for p in agents_root.iterdir() if p.is_dir()]):
            agent_id = agent_dir.name
            md_path = mnemosyne_dir(project_id) / "agent_profiles" / f"{agent_id}.md"
            role = "No role summary."
            if md_path.exists():
                text = md_path.read_text(encoding="utf-8").strip()
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                if lines:
                    role = lines[0].replace("#", "").strip()
                    for i, ln in enumerate(lines):
                        if ("本体职责" in ln) or ("自身职责" in ln):
                            for j in range(i + 1, len(lines)):
                                cand = lines[j]
                                if cand.startswith("#"):
                                    break
                                role = cand[:120]
                                break
                            break
                    else:
                        for ln in lines[1:]:
                            if not ln.startswith("#"):
                                role = ln[:120]
                                break
            results.append(f"- {agent_id}: {role}")

        return "\n".join(results)
    except Exception as e:
        return format_comm_error(
            "Communication Error",
            str(e),
            "Verify project agents directory exists and mnemosyne profiles are readable.",
            caller_id,
            project_id,
        )
