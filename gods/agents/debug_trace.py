"""
Structured pulse trace logging for runtime debugging.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gods.config import runtime_config


def _clip(value: Any, max_chars: int = 240) -> str:
    text = str(value if value is not None else "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...(truncated)"


class PulseTraceLogger:
    def __init__(self, project_id: str, agent_id: str, pulse_id: str, reason: str):
        self.project_id = project_id
        self.agent_id = agent_id
        self.pulse_id = pulse_id
        self.reason = reason
        self.started_at = time.time()
        self.events: list[dict] = []
        self._seq = 0

    def _enabled(self) -> bool:
        proj = runtime_config.projects.get(self.project_id)
        return bool(getattr(proj, "debug_trace_enabled", True) if proj else True)

    def _full_content(self) -> bool:
        proj = runtime_config.projects.get(self.project_id)
        return bool(getattr(proj, "debug_trace_full_content", True) if proj else True)

    def event(self, kind: str, **fields):
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
        path = Path("projects") / self.project_id / "agents" / self.agent_id / "debug" / "pulse_trace.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    @staticmethod
    def clip(value: Any, max_chars: int = 240) -> str:
        return _clip(value, max_chars=max_chars)
