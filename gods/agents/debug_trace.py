"""
Structured pulse trace logging for runtime debugging.
"""
from __future__ import annotations

import json
import time
from typing import Any

from gods.config import runtime_config
from gods.paths import runtime_debug_dir


def _clip(value: Any, max_chars: int = 240) -> str:
    """
    Truncates a string value to a maximum length, appending a suffix if clipped.
    """
    text = str(value if value is not None else "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...(truncated)"


class PulseTraceLogger:
    """
    Logger for tracking detailed events during an agent's pulse execution.
    """
    def __init__(self, project_id: str, agent_id: str, pulse_id: str, reason: str):
        """
        Initializes the logger with project, agent, and pulse context.
        """
        self.project_id = project_id
        self.agent_id = agent_id
        self.pulse_id = pulse_id
        self.reason = reason
        self.started_at = time.time()
        self.events: list[dict] = []
        self._seq = 0

    def _enabled(self) -> bool:
        """
        Checks if pulse tracing is enabled for the current project.
        """
        proj = runtime_config.projects.get(self.project_id)
        return bool(getattr(proj, "debug_trace_enabled", True) if proj else True)

    def _full_content(self) -> bool:
        """
        Checks if full content tracing is enabled (without truncation).
        """
        proj = runtime_config.projects.get(self.project_id)
        return bool(getattr(proj, "debug_trace_full_content", True) if proj else True)

    def event(self, kind: str, **fields):
        """
        Records a specific event kind with associated metadata fields.
        """
        if not self._enabled():
            return
        if not self._full_content():
            # Keep payload bounded when full-content mode is off.
            for key, value in list(fields.items()):
                if isinstance(value, str):
                    fields[key] = _clip(value, max_chars=300)
        self._seq += 1
        payload = {
            "seq": self._seq,
            "ts": time.time(),
            "kind": kind,
        }
        payload.update(fields)
        self.events.append(payload)

    def flush(self):
        """
        Persists the recorded events to the pulse_trace.jsonl file.
        """
        if not self._enabled():
            return
        proj = runtime_config.projects.get(self.project_id)
        max_events = int(getattr(proj, "debug_trace_max_events", 200) if proj else 200)
        max_events = max(20, min(max_events, 2000))
        events = self.events[-max_events:]

        trace = {
            "ts": time.time(),
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "pulse_id": self.pulse_id,
            "reason": self.reason,
            "duration_sec": round(time.time() - self.started_at, 3),
            "event_count": len(events),
            "events": events,
        }
        path = runtime_debug_dir(self.project_id, self.agent_id) / "pulse_trace.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    @staticmethod
    def clip(value: Any, max_chars: int = 240) -> str:
        """
        Static access to the internal _clip utility.
        """
        return _clip(value, max_chars=max_chars)
