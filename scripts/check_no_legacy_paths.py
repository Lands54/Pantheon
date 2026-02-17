#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

INCLUDE_SUFFIX = {".py", ".md", ".txt", ".sh"}
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "frontend/node_modules",
    "archive",
    "archives",
    "projects",
    ".venv",
}

PATTERNS = [
    ("compat_shim", re.compile(r"Compatibility shim", re.I), {"docs", "scripts"}),
    ("api_scheduler", re.compile(r"\bapi\.scheduler\b"), {"docs", "scripts"}),
    ("broadcast_model", re.compile(r"\bBroadcastRequest\b"), set()),
    ("old_build_context", re.compile(r"\bdef\s+build_context\s*\("), {"tests"}),
    ("old_record_memory_event", re.compile(r"\brecord_memory_event\s*\("), set()),
    ("removed_cli_cmd", re.compile(r"subparsers\.add_parser\(\"(broadcast|prayers|pulse)\"\)"), set()),
    ("removed_inbox_events", re.compile(r"inbox_sub\.add_parser\(\"events\"\)"), set()),
    ("removed_angelia_events_routes", re.compile(r"/angelia/events"), {"docs", "scripts"}),
    ("removed_detach_project_routes", re.compile(r"/projects/\{project_id\}/detach/"), {"docs", "scripts"}),
    ("removed_pulse_queue_store", re.compile(r"pulse_events\.jsonl"), {"docs", "scripts", "gods/events"}),
    ("removed_inbox_compat_api", re.compile(r"\b(enqueue_inbox_event|list_inbox_events|transition_inbox_state|take_deliverable_inbox_events|mark_inbox_events_handled)\b"), {"scripts"}),
    ("removed_legacy_config_field", re.compile(r"\b(inbox_event_enabled|queue_idle_heartbeat_sec)\b"), {"docs", "gods/events/migrate.py", "tests", "scripts"}),
    ("removed_legacy_state_window_path", re.compile(r"\blegacy_agent_state_window_path\b"), {"tests", "scripts"}),
    ("removed_confess_route", re.compile(r"@router\.post\(\"/confess\"\)|/confess\b"), {"tests", "docs", "scripts"}),
    ("removed_send_to_human_tool", re.compile(r"\bsend_to_human\b"), {"docs", "tests", "scripts"}),
    ("forbid_hermes_direct_iris_enqueue", re.compile(r"from\s+gods\.iris\.facade\s+import\s+enqueue_message"), {"scripts", "tests"}),
    ("removed_phase_runtime_module", re.compile(r"gods\.agents\.phase_runtime"), {"docs", "scripts"}),
    ("removed_legacy_phase_strategy_names", re.compile(r"\b(strict_triad|iterative_action)\b"), {"docs", "scripts"}),
    ("removed_phase_mode_enabled", re.compile(r"\bphase_mode_enabled\b"), {"docs", "scripts"}),
]


def _excluded(path: pathlib.Path) -> bool:
    s = str(path)
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    return False


def main() -> int:
    hits: list[str] = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in INCLUDE_SUFFIX or _excluded(p):
            continue
        rel = p.relative_to(ROOT)
        text = p.read_text(encoding="utf-8", errors="ignore")
        for name, pat, allowed_prefixes in PATTERNS:
            if allowed_prefixes and any(str(rel).startswith(prefix + "/") or str(rel) == prefix for prefix in allowed_prefixes):
                continue
            for idx, line in enumerate(text.splitlines(), start=1):
                if pat.search(line):
                    hits.append(f"{name}: {rel}:{idx}: {line.strip()}")

    if hits:
        print("Legacy path guard failed:")
        for h in hits:
            print(h)
        return 1
    print("Legacy path guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
