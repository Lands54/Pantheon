"""PulseLedger: append-only pulse event source of truth."""
from __future__ import annotations

import json
import logging
import os
import fcntl
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

from gods.paths import mnemosyne_dir

logger = logging.getLogger(__name__)

PulseKind = Literal[
    "pulse.start",
    "trigger.event",
    "trigger.mail",
    "llm.response",
    "tool.call",
    "tool.result",
    "pulse.finish",
]
PulseOrigin = Literal["angelia", "internal", "external"]


class PulseLedgerEntry(TypedDict):
    seq: int
    project_id: str
    agent_id: str
    pulse_id: str
    kind: PulseKind
    ts: float
    payload: dict[str, Any]
    origin: PulseOrigin
    trace_id: str


@dataclass
class PulseFrameRaw:
    """Raw frame grouped from ledger entries by pulse_id."""
    pulse_id: str
    start: dict[str, Any] | None = None
    triggers: list[dict[str, Any]] = field(default_factory=list)
    llm: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    finish: dict[str, Any] | None = None

    @property
    def is_complete(self) -> bool:
        """A pulse is complete if it has both start and finish entries."""
        return self.start is not None and self.finish is not None

    @property
    def has_triggers(self) -> bool:
        """A pulse has triggers only when trigger.event/trigger.mail exists."""
        return bool(self.triggers)


_KIND_ORDER: dict[str, int] = {
    "pulse.start": 0,
    "trigger.event": 1,
    "trigger.mail": 1,
    "llm.response": 2,
    "tool.call": 3,
    "tool.result": 4,
    "pulse.finish": 5,
}


def _ledger_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "pulse_ledger" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _seq_path(project_id: str, agent_id: str) -> Path:
    p = mnemosyne_dir(project_id) / "pulse_ledger_seq" / f"{agent_id}.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _next_seq(project_id: str, agent_id: str, n: int = 1) -> int:
    path = _seq_path(project_id, agent_id)
    with path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            raw = str(f.read() or "").strip()
            cur = int(raw) if raw.isdigit() else 0
            nxt = max(1, cur + 1)
            end = nxt + max(1, int(n)) - 1
            f.seek(0)
            f.truncate()
            f.write(str(end))
            f.flush()
            os.fsync(f.fileno())
            return nxt
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def append_pulse_entry(
    project_id: str,
    agent_id: str,
    *,
    pulse_id: str,
    kind: PulseKind,
    payload: dict[str, Any] | None = None,
    origin: PulseOrigin = "internal",
    ts: float | None = None,
    trace_id: str = "",
) -> PulseLedgerEntry:
    """Append a single pulse entry to the ledger."""
    pid = str(pulse_id or "").strip()
    if not pid:
        raise ValueError("pulse_id is required")
    row: PulseLedgerEntry = {
        "seq": int(_next_seq(project_id, agent_id, 1)),
        "project_id": str(project_id),
        "agent_id": str(agent_id),
        "pulse_id": pid,
        "kind": kind,
        "ts": float(ts if ts is not None else time.time()),
        "payload": dict(payload or {}),
        "origin": origin,
        "trace_id": str(trace_id or ""),
    }
    path = _ledger_path(project_id, agent_id)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def append_pulse_entries(
    project_id: str,
    agent_id: str,
    rows: list[dict[str, Any]] | None,
) -> list[PulseLedgerEntry]:
    """Append multiple pulse entries atomically to the ledger."""
    items = [dict(x) for x in list(rows or []) if isinstance(x, dict)]
    if not items:
        return []
    start = _next_seq(project_id, agent_id, len(items))
    out: list[PulseLedgerEntry] = []
    now = time.time()
    for i, row in enumerate(items):
        pid = str(row.get("pulse_id", "") or "").strip()
        if not pid:
            raise ValueError("pulse_id is required in append_pulse_entries")
        kind = str(row.get("kind", "") or "").strip()
        if kind not in _KIND_ORDER:
            raise ValueError(f"invalid pulse ledger kind: {kind}")
        out.append(
            {
                "seq": int(start + i),
                "project_id": str(project_id),
                "agent_id": str(agent_id),
                "pulse_id": pid,
                "kind": kind,  # type: ignore[typeddict-item]
                "ts": float(row.get("ts") or now),
                "payload": dict(row.get("payload", {}) or {}),
                "origin": str(row.get("origin", "internal") or "internal"),  # type: ignore[typeddict-item]
                "trace_id": str(row.get("trace_id", "") or ""),
            }
        )
    path = _ledger_path(project_id, agent_id)
    with path.open("a", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out


def list_pulse_entries(
    project_id: str,
    agent_id: str,
    *,
    from_seq: int = 0,
    to_seq: int = 0,
    limit: int = 4000,
    since_ts: float = 0.0,
) -> list[PulseLedgerEntry]:
    """Read entries from the ledger with seq/ts/limit filtering."""
    path = _ledger_path(project_id, agent_id)
    if not path.exists():
        return []
    lo = max(0, int(from_seq or 0))
    hi = int(to_seq or 0)
    lim = max(1, min(int(limit or 4000), 200000))
    sts = float(since_ts or 0.0)
    out: list[PulseLedgerEntry] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            seq = int(row.get("seq", 0) or 0)
            if seq <= lo:
                continue
            if hi > 0 and seq > hi:
                continue
            ts = float(row.get("ts", 0.0) or 0.0)
            if sts > 0 and ts < sts:
                continue
            try:
                kind = str(row.get("kind", "") or "")
                if kind not in _KIND_ORDER:
                    continue
                out.append(
                    {
                        "seq": seq,
                        "project_id": str(row.get("project_id", project_id) or project_id),
                        "agent_id": str(row.get("agent_id", agent_id) or agent_id),
                        "pulse_id": str(row.get("pulse_id", "") or ""),
                        "kind": kind,  # type: ignore[typeddict-item]
                        "ts": ts,
                        "payload": dict(row.get("payload", {}) or {}),
                        "origin": str(row.get("origin", "internal") or "internal"),  # type: ignore[typeddict-item]
                        "trace_id": str(row.get("trace_id", "") or ""),
                    }
                )
            except Exception:
                continue
    return out[-lim:]


def group_pulses(entries: list[PulseLedgerEntry]) -> list[PulseFrameRaw]:
    """Group flat ledger entries into PulseFrameRaw structures by pulse_id."""
    frames: dict[str, PulseFrameRaw] = {}
    order: list[str] = []
    rows = sorted(
        [dict(x) for x in list(entries or []) if isinstance(x, dict)],
        key=lambda x: (int(x.get("seq", 0) or 0), float(x.get("ts", 0.0) or 0.0), _KIND_ORDER.get(str(x.get("kind", "")), 99)),
    )
    for row in rows:
        pid = str(row.get("pulse_id", "") or "").strip()
        if not pid:
            continue
        if pid not in frames:
            frames[pid] = PulseFrameRaw(pulse_id=pid)
            order.append(pid)
        fr = frames[pid]
        kind = str(row.get("kind", "") or "")
        if kind == "pulse.start":
            fr.start = row
        elif kind in {"trigger.event", "trigger.mail"}:
            fr.triggers.append(row)
        elif kind == "llm.response":
            fr.llm.append(row)
        elif kind in {"tool.call", "tool.result"}:
            fr.tools.append(row)
        elif kind == "pulse.finish":
            fr.finish = row
    return [frames[pid] for pid in order]


def discard_incomplete_frames(
    frames: list[PulseFrameRaw],
    *,
    allow_open_pulse_id: str = "",
) -> list[PulseFrameRaw]:
    """Discard frames that are missing their pulse.start entry.

    A frame without pulse.start is never usable for context construction.
    This typically happens when:
    1. list_pulse_entries tail-truncation (out[-lim:]) clips the pulse.start
       of a frame whose later entries (llm.response, pulse.finish) survive.
    2. The pulse.start write itself failed (network error, etc).

    In both cases the frame is incomplete and should be silently dropped.
    The allow_open_pulse_id parameter exempts the currently-running pulse
    since its entries may still be arriving.
    """
    if not frames:
        return frames
    open_pid = str(allow_open_pulse_id or "").strip()
    kept: list[PulseFrameRaw] = []
    for fr in frames:
        if fr.start is not None:
            kept.append(fr)
        elif fr.pulse_id == open_pid and open_pid:
            # Current open pulse may be in-flight; keep it.
            kept.append(fr)
        else:
            logger.debug(
                "PULSE_DISCARD_INCOMPLETE: dropping pulse %s "
                "(no pulse.start — likely truncation artifact or write failure)",
                fr.pulse_id,
            )
    return kept


# Keep backward-compatible alias
trim_truncated_head = discard_incomplete_frames


@dataclass
class PulseIntegrityReport:
    """Structured integrity report with severity levels."""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    @property
    def all_issues(self) -> list[str]:
        return self.errors + self.warnings


def validate_pulse_integrity(
    frames: list[PulseFrameRaw],
    *,
    allow_open_pulse_id: str = "",
) -> PulseIntegrityReport:
    """Validate pulse frames with severity-aware reporting.

    Returns a PulseIntegrityReport with:
    - errors: critical issues that indicate real data corruption
    - warnings: benign issues (e.g. open pulse without finish)
    """
    report = PulseIntegrityReport()
    open_pid = str(allow_open_pulse_id or "").strip()

    for fr in list(frames or []):
        pid = str(fr.pulse_id or "")

        # Missing pulse.start is an error (should be caught by trim_truncated_head first)
        if fr.start is None:
            report.errors.append(f"{pid}: missing pulse.start")

        # Missing pulse.finish: warning for open pulse, error for historical closed pulse
        if fr.finish is None:
            if pid == open_pid:
                report.warnings.append(f"{pid}: open pulse (no pulse.finish yet)")
            else:
                report.warnings.append(f"{pid}: missing pulse.finish (may be in-flight)")

        # Empty trigger: pulse.start is lifecycle marker, not trigger cause.
        if not fr.triggers:
            report.errors.append(f"{pid}: empty trigger (no trigger.event/mail)")

        # Tool call/result pairing check
        calls: set[str] = set()
        for row in fr.tools:
            kind = str(row.get("kind", "") or "")
            pld = dict(row.get("payload", {}) or {})
            cid = str(pld.get("call_id", "") or "").strip()
            if not cid:
                continue
            if kind == "tool.call":
                calls.add(cid)
            elif kind == "tool.result" and cid not in calls:
                report.warnings.append(f"{pid}: tool.result without tool.call call_id={cid}")

    return report
