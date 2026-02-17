#!/usr/bin/env python3
"""Basic integrity checks for unified event bus files."""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED = {
    "event_id",
    "project_id",
    "domain",
    "event_type",
    "state",
    "priority",
    "payload",
    "attempt",
    "max_attempts",
    "dedupe_key",
    "created_at",
    "available_at",
    "meta",
}


def check_file(path: Path) -> tuple[int, list[str]]:
    errs: list[str] = []
    count = 0
    if not path.exists():
        return 0, errs
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        count += 1
        try:
            row = json.loads(line)
        except Exception:
            errs.append(f"{path}:{i}: invalid json")
            continue
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            errs.append(f"{path}:{i}: missing {','.join(missing)}")
    return count, errs


def main() -> int:
    total = 0
    errs: list[str] = []
    root = Path("projects")
    for p in sorted([x for x in root.iterdir() if x.is_dir()] if root.exists() else []):
        c, e = check_file(p / "runtime" / "events.jsonl")
        total += c
        errs.extend(e)
    payload = {"total_events": total, "error_count": len(errs), "errors": errs[:200]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if errs:
        print(f"EVENT_BUS_INTEGRITY_ERROR_COUNT {len(errs)}")
        return 1
    print("EVENT_BUS_INTEGRITY_ERROR_COUNT 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
