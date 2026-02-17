"""Migration helpers from legacy pulse/inbox files to Angelia events."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from . import policy, store
from gods.angelia.models import AngeliaEvent, AngeliaEventState


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def migrate_to_angelia(project_id: str) -> dict:
    _ = (policy, store, AngeliaEvent, AngeliaEventState, _read_jsonl, json, shutil, time, Path)
    # Single-source switch: migration is no longer needed because Iris mail_events.jsonl is authoritative.
    return {"project_id": project_id, "status": "skipped", "reason": "single_source_iris", "events": 0}
