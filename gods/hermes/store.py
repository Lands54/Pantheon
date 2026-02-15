"""Project-scoped filesystem store for Hermes."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def _project_protocol_dir(project_id: str) -> Path:
    path = Path("projects") / project_id / "protocols"
    path.mkdir(parents=True, exist_ok=True)
    return path


def registry_path(project_id: str) -> Path:
    return _project_protocol_dir(project_id) / "registry.json"


def invocations_path(project_id: str) -> Path:
    return _project_protocol_dir(project_id) / "invocations.jsonl"


def contracts_path(project_id: str) -> Path:
    return _project_protocol_dir(project_id) / "contracts.json"


def jobs_dir(project_id: str) -> Path:
    path = _project_protocol_dir(project_id) / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def job_path(project_id: str, job_id: str) -> Path:
    return jobs_dir(project_id) / f"{job_id}.json"


def runtime_dir(project_id: str) -> Path:
    path = Path("projects") / project_id / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ports_path(project_id: str) -> Path:
    return runtime_dir(project_id) / "ports.json"


def load_registry(project_id: str) -> dict:
    path = registry_path(project_id)
    if not path.exists():
        return {"protocols": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"protocols": []}


def save_registry(project_id: str, payload: dict):
    path = registry_path(project_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_contracts(project_id: str) -> dict:
    path = contracts_path(project_id)
    if not path.exists():
        return {"contracts": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"contracts": []}


def save_contracts(project_id: str, payload: dict):
    path = contracts_path(project_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_invocation(project_id: str, payload: dict):
    path = invocations_path(project_id)
    row = dict(payload)
    row.setdefault("timestamp", time.time())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def list_invocations(project_id: str, name: str = "", limit: int = 100) -> list[dict]:
    path = invocations_path(project_id)
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if name and row.get("name") != name:
                continue
            out.append(row)
    return out[-max(1, min(limit, 1000)):]


def save_job(project_id: str, job_id: str, payload: dict):
    path = job_path(project_id, job_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_job(project_id: str, job_id: str) -> dict[str, Any] | None:
    path = job_path(project_id, job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_ports(project_id: str) -> dict:
    path = ports_path(project_id)
    if not path.exists():
        return {"leases": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"leases": []}


def save_ports(project_id: str, payload: dict):
    path = ports_path(project_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
