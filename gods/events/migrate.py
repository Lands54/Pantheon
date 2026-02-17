"""Startup legacy-file guards for strict zero-compat mode."""
from __future__ import annotations

import json
from pathlib import Path

from gods.events.models import EventState


_LEGACY_RUNTIME_FILES = (
    "mail_events.jsonl",
    "angelia_events.jsonl",
    "pulse_events.jsonl",
)


def _project_runtime(project_id: str) -> Path:
    return Path("projects") / project_id / "runtime"


def assert_no_legacy_files(project_id: str):
    rt = _project_runtime(project_id)
    exists = []
    for name in _LEGACY_RUNTIME_FILES:
        p = rt / name
        if p.exists() and p.stat().st_size > 0:
            exists.append(str(p))
    if exists:
        msg = (
            "legacy runtime files detected; zero-compat mode blocks startup. "
            "remove/migrate these files manually: " + ", ".join(exists)
        )
        raise RuntimeError(msg)
    ep = rt / "events.jsonl"
    if ep.exists():
        allowed = {x.value for x in EventState}
        bad_states: set[str] = set()
        for line in ep.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            st = str(row.get("state", "")).strip()
            if st and st not in allowed:
                bad_states.add(st)
        if bad_states:
            raise RuntimeError(
                "events.jsonl contains unsupported legacy states in strict mode: "
                + ", ".join(sorted(bad_states))
            )


def assert_no_legacy_files_all_projects() -> dict[str, str]:
    root = Path("projects")
    rows: dict[str, str] = {}
    if not root.exists():
        return rows
    for p in sorted([x for x in root.iterdir() if x.is_dir()]):
        assert_no_legacy_files(p.name)
        rows[p.name] = "ok"
    return rows
