"""
Gods Tools - Communication Module
Agent-to-agent and agent-to-human communication tools.
"""
from pathlib import Path
import json
import fcntl
import time
from langchain.tools import tool


@tool
def check_inbox(caller_id: str, project_id: str = "default") -> str:
    """Check your own divine inbox for private revelations in the current project."""
    project_root = Path(__file__).parent.parent.parent.absolute()
    buffer_dir = project_root / "projects" / project_id / "buffers"
    buffer_path = buffer_dir / f"{caller_id}.jsonl"
    
    if not buffer_path.exists():
        return json.dumps([])
    
    messages = []
    with open(buffer_path, "r+", encoding="utf-8") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX)
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))
            f.seek(0)
            f.truncate()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return json.dumps(messages, ensure_ascii=False)


@tool
def send_message(to_id: str, message: str, caller_id: str, project_id: str = "default") -> str:
    """Send a private revelation to another Being within the same project."""
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


@tool
def send_to_human(message: str, caller_id: str = "default") -> str:
    """
    Sacred Prayer. Send a private message to the Human Overseer.
    Use this for direct reporting or when human intervention is required.
    """
    project_root = Path(__file__).parent.parent.parent.absolute()
    buffer_dir = project_root / "gods_platform" / "buffers"
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
