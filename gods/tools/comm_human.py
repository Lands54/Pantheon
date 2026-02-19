"""Human/social communication tools."""
from __future__ import annotations

import json

from langchain_core.tools import tool

from gods.angelia import facade as angelia_facade
from gods.hestia import facade as hestia_facade
from gods.identity import is_valid_agent_id
from gods.interaction import facade as interaction_facade
from gods.interaction.contracts import EVENT_MESSAGE_SENT
from gods.mnemosyne import facade as mnemosyne_facade
from gods.paths import mnemosyne_dir, project_dir
from gods.tools.comm_common import format_comm_error


@tool
def send_message(
    to_id: str,
    title: str,
    message: str,
    caller_id: str,
    project_id: str = "default",
    attachments: str = "[]",
) -> str:
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
        try:
            raw = json.loads(str(attachments or "[]"))
        except Exception as e:
            return format_comm_error(
                "Message Error",
                f"attachments must be valid JSON array: {e}",
                'Use attachments like ["artf_xxx","artf_yyy"].',
                caller_id,
                project_id,
            )
        if not isinstance(raw, list):
            return format_comm_error(
                "Message Error",
                "attachments must be a JSON array.",
                'Use attachments like ["artf_xxx","artf_yyy"].',
                caller_id,
                project_id,
            )
        attachment_ids: list[str] = []
        for item in raw:
            aid = str(item or "").strip()
            if not aid:
                continue
            if "/" in aid or aid.startswith("."):
                return format_comm_error(
                    "Message Error",
                    f"invalid attachment id '{aid}': path-like values are forbidden.",
                    "Pass artifact_id only, not file paths.",
                    caller_id,
                    project_id,
                )
            if not mnemosyne_facade.is_valid_artifact_id(aid):
                return format_comm_error(
                    "Message Error",
                    f"invalid attachment id '{aid}'.",
                    "Pass artifact_id only, e.g. artf_<sha12>_<ts>.",
                    caller_id,
                    project_id,
                )
            try:
                ref = mnemosyne_facade.head_artifact(aid, caller_id, project_id)
            except Exception as e:
                return format_comm_error(
                    "Message Error",
                    f"attachment '{aid}' is not accessible: {e}",
                    "Ensure artifact exists and caller has ACL access.",
                    caller_id,
                    project_id,
                )
            if str(getattr(ref, "scope", "")) != "agent":
                return format_comm_error(
                    "Message Error",
                    f"attachment '{aid}' must be agent-scope artifact.",
                    "Use upload_artifact tool (default agent scope) to create private attachment first.",
                    caller_id,
                    project_id,
                )
            attachment_ids.append(aid)
        attachment_ids = list(dict.fromkeys(attachment_ids))
        if not hestia_facade.can_message(project_id=project_id, from_id=caller_id, to_id=to_id):
            return format_comm_error(
                "Message Blocked",
                f"social graph denies route {caller_id} -> {to_id}.",
                "Use Hestia API/CLI to update adjacency matrix before sending.",
                caller_id,
                project_id,
            )

        weights = angelia_facade.get_priority_weights(project_id)
        trigger = angelia_facade.is_mail_event_wakeup_enabled(project_id)
        queued = interaction_facade.submit_message_event(
            project_id=project_id,
            to_id=to_id,
            sender_id=caller_id,
            title=title,
            content=message,
            msg_type="private",
            trigger_pulse=trigger,
            priority=int(weights.get("mail_event", 100)),
            event_type=EVENT_MESSAGE_SENT,
            attachments=attachment_ids,
        )
        return (
            f"Revelation sent to {to_id}. "
            f"title={title}, "
            f"event_id={queued.get('event_id', '')}, "
            f"attachments_count={len(attachment_ids)}, "
            f"wakeup_sent={str(bool(queued.get('wakeup_sent', False))).lower()}, "
            "initial_state=queued(interaction)"
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

        visible = set(hestia_facade.list_reachable_agents(project_id=project_id, caller_id=caller_id))
        restrict_by_graph = bool(is_valid_agent_id(caller_id))
        results = []
        for agent_dir in sorted([p for p in agents_root.iterdir() if p.is_dir()]):
            agent_id = agent_dir.name
            if not is_valid_agent_id(agent_id):
                continue
            if restrict_by_graph and agent_id not in visible:
                continue
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

        if not results:
            if restrict_by_graph:
                return "No reachable agents in Hestia social graph."
            return "No agents found in this project."
        return "\n".join(results)
    except Exception as e:
        return format_comm_error(
            "Communication Error",
            str(e),
            "Verify project agents directory exists and mnemosyne profiles are readable.",
            caller_id,
            project_id,
        )
