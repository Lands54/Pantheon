"""
Gods Tools - Communication Module
Agent-to-agent and agent-to-human communication tools.
"""
from pathlib import Path
import json
import fcntl
import time
from langchain.tools import tool


def _format_comm_error(title: str, reason: str, suggestion: str, caller_id: str, project_id: str) -> str:
    project_root = Path(__file__).parent.parent.parent.absolute()
    cwd = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
    return (
        f"[Current CWD: {cwd}] "
        f"{title}: {reason}\n"
        f"Suggested next step: {suggestion}"
    )


def _inbox_guard_path(caller_id: str, project_id: str) -> Path:
    project_root = Path(__file__).parent.parent.parent.absolute()
    guard_dir = project_root / "projects" / project_id / "buffers"
    guard_dir.mkdir(parents=True, exist_ok=True)
    return guard_dir / f"{caller_id}_inbox_guard.json"


def _load_inbox_guard(caller_id: str, project_id: str) -> dict:
    path = _inbox_guard_path(caller_id, project_id)
    if not path.exists():
        return {"warned_empty": False, "blocked": False}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"warned_empty": False, "blocked": False}


def _save_inbox_guard(caller_id: str, project_id: str, state: dict):
    path = _inbox_guard_path(caller_id, project_id)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def reset_inbox_guard(caller_id: str, project_id: str):
    """
    Called by non-inbox actions: allow future inbox checks again.
    """
    _save_inbox_guard(caller_id, project_id, {"warned_empty": False, "blocked": False})


@tool
def check_inbox(caller_id: str, project_id: str = "default") -> str:
    """Check your own divine inbox for private revelations in the current project."""
    try:
        guard = _load_inbox_guard(caller_id, project_id)
        if guard.get("blocked"):
            return (
                _format_comm_error(
                    "Divine Warning",
                    "Inbox checks are temporarily blocked after repeated empty checks.",
                    "Perform one non-inbox action (read/write/list/run/send), then check inbox again.",
                    caller_id,
                    project_id,
                )
            )

        project_root = Path(__file__).parent.parent.parent.absolute()
        buffer_dir = project_root / "projects" / project_id / "buffers"
        buffer_path = buffer_dir / f"{caller_id}.jsonl"

        if not buffer_path.exists():
            if not guard.get("warned_empty", False):
                _save_inbox_guard(caller_id, project_id, {"warned_empty": True, "blocked": False})
                return (
                    "Inbox Empty Warning: no new messages. "
                    "If you check again without doing other work, inbox checks will be blocked once."
                )
            _save_inbox_guard(caller_id, project_id, {"warned_empty": True, "blocked": True})
            return (
                _format_comm_error(
                    "Divine Warning",
                    "Inbox is still empty and now temporarily blocked.",
                    "Do one non-inbox action first, then check again.",
                    caller_id,
                    project_id,
                )
            )

        messages = []
        read_path = buffer_dir / f"{caller_id}_read.jsonl"
        read_timestamp = time.time()

        with open(buffer_path, "r+", encoding="utf-8") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
                for line in f:
                    if line.strip():
                        msg = json.loads(line)
                        msg["read_at"] = read_timestamp
                        messages.append(msg)

                # Append read messages to history
                if messages:
                    with open(read_path, "a", encoding="utf-8") as rf:
                        fcntl.flock(rf, fcntl.LOCK_EX)
                        for m in messages:
                            rf.write(json.dumps(m, ensure_ascii=False) + "\n")
                        fcntl.flock(rf, fcntl.LOCK_UN)

                f.seek(0)
                f.truncate()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

        if messages:
            reset_inbox_guard(caller_id, project_id)
        else:
            if not guard.get("warned_empty", False):
                _save_inbox_guard(caller_id, project_id, {"warned_empty": True, "blocked": False})
                return (
                    "Inbox Empty Warning: no new messages. "
                    "If you check again without doing other work, inbox checks will be blocked once."
                )
            _save_inbox_guard(caller_id, project_id, {"warned_empty": True, "blocked": True})
            return (
                _format_comm_error(
                    "Divine Warning",
                    "Inbox is still empty and now temporarily blocked.",
                    "Do one non-inbox action first, then check again.",
                    caller_id,
                    project_id,
                )
            )

        return json.dumps(messages, ensure_ascii=False)
    except Exception as e:
        return _format_comm_error(
            "Communication Error",
            str(e),
            "Retry inbox check; if it persists, verify buffer file permissions.",
            caller_id,
            project_id,
        )


@tool
def send_message(to_id: str, message: str, caller_id: str, project_id: str = "default") -> str:
    """Send a private revelation to another Being within the same project."""
    try:
        if not to_id.strip():
            return _format_comm_error(
                "Message Error",
                "Target agent id is empty.",
                "Set to_id to a valid agent id, e.g. 'sheep' or 'ground'.",
                caller_id,
                project_id,
            )
        if not message.strip():
            return _format_comm_error(
                "Message Error",
                "Message content is empty.",
                "Provide a concrete message payload before sending.",
                caller_id,
                project_id,
            )

        project_root = Path(__file__).parent.parent.parent.absolute()
        buffer_dir = project_root / "projects" / project_id / "buffers"
        buffer_dir.mkdir(parents=True, exist_ok=True)

        target_buffer = buffer_dir / f"{to_id}.jsonl"
        msg_data = {"timestamp": time.time(), "from": caller_id, "type": "private", "content": message}

        with open(target_buffer, "a", encoding="utf-8") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps(msg_data, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return f"Revelation sent to {to_id}"
    except Exception as e:
        return _format_comm_error(
            "Communication Error",
            str(e),
            "Retry send_message and verify project buffers are writable.",
            caller_id,
            project_id,
        )


@tool
def send_to_human(message: str, caller_id: str, project_id: str = "default") -> str:
    """
    Sacred Prayer. Send a private message to the Human Overseer.
    Use this for direct reporting or when human intervention is required.
    """
    try:
        if not message.strip():
            return _format_comm_error(
                "Message Error",
                "Prayer message is empty.",
                "Provide what you need to report or request from human.",
                caller_id,
                project_id,
            )

        project_root = Path(__file__).parent.parent.parent.absolute()
        buffer_dir = project_root / "projects" / project_id / "buffers"
        buffer_dir.mkdir(parents=True, exist_ok=True)

        # Store human messages in a specific buffer
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
        return _format_comm_error(
            "Communication Error",
            str(e),
            "Retry send_to_human and verify project buffers are writable.",
            caller_id,
            project_id,
        )


@tool
def finalize(caller_id: str, project_id: str = "default") -> str:
    """
    Signal explicit task finalization for the current pulse.
    This is an intentional no-output control signal.
    """
    return ""


@tool
def post_to_synod(reason: str, message: str, caller_id: str = "default") -> str:
    """
    Escalate to Public Synod. Use this when you cannot resolve an issue privately or need 
    collective wisdom. This will be visible to ALL Beings.
    """
    # This will be handled by the server/simulation orchestrator to trigger a global round
    return f"[[SYNOD_RESONANCE]] Requesting public discussion for: {reason}. Content: {message}"


@tool
def abstain_from_synod(reason: str, caller_id: str = "default") -> str:
    """
    Abstain from current discussion. Use this if the topic is irrelevant to your 
    domain or you have nothing to contribute. You will be skipped for the remainder 
    of this Public Synod thread.
    """
    return f"[[ABSTAIN]] Reason: {reason}"


@tool
def record_protocol(
    topic: str,
    relation: str,
    object: str,
    clause: str,
    counterparty: str = "",
    status: str = "agreed",
    caller_id: str = "default",
    project_id: str = "default",
) -> str:
    """
    Record a negotiated protocol clause in structured form for knowledge graph extraction.
    """
    try:
        if not topic.strip() or not relation.strip() or not object.strip() or not clause.strip():
            return _format_comm_error(
                "Protocol Error",
                "topic/relation/object/clause cannot be empty.",
                "Provide all required protocol fields before recording.",
                caller_id,
                project_id,
            )

        project_root = Path(__file__).parent.parent.parent.absolute()
        proto_dir = project_root / "projects" / project_id / "protocols"
        proto_dir.mkdir(parents=True, exist_ok=True)
        event_file = proto_dir / "events.jsonl"

        now = time.time()
        protocol_id = f"p_{int(now * 1000)}_{caller_id}"
        entry = {
            "timestamp": now,
            "protocol_id": protocol_id,
            "project_id": project_id,
            "subject": caller_id,
            "counterparty": counterparty,
            "topic": topic,
            "relation": relation,
            "object": object,
            "clause": clause,
            "status": status,
        }

        with open(event_file, "a", encoding="utf-8") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

        return f"Protocol recorded: {protocol_id} ({caller_id} -[{relation}]-> {object})"
    except Exception as e:
        return _format_comm_error(
            "Protocol Error",
            str(e),
            "Retry record_protocol and verify protocol directory is writable.",
            caller_id,
            project_id,
        )


@tool
def list_agents(caller_id: str, project_id: str = "default") -> str:
    """
    List all agents in current project with a short role summary from their agent.md.
    """
    try:
        agents_root = Path("projects") / project_id / "agents"
        if not agents_root.exists():
            return "No agents found in this project."

        results = []
        for agent_dir in sorted([p for p in agents_root.iterdir() if p.is_dir()]):
            agent_id = agent_dir.name
            md_path = agent_dir / "agent.md"
            role = "No role summary."
            if md_path.exists():
                text = md_path.read_text(encoding="utf-8").strip()
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                if lines:
                    role = lines[0].replace("#", "").strip()
                    # Prefer explicit "本体职责/自身职责" section content.
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
        return _format_comm_error(
            "Communication Error",
            str(e),
            "Verify project agents directory exists and agent.md files are readable.",
            caller_id,
            project_id,
        )
