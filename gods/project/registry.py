"""Runtime project registry (project list + current project)."""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path
from typing import Any, Iterable

from gods.paths import projects_root


def _runtime_root() -> Path:
    p = projects_root() / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _registry_path() -> Path:
    return _runtime_root() / "projects_registry.json"


def _lock_path() -> Path:
    p = _runtime_root() / "projects_registry.lock"
    p.touch(exist_ok=True)
    return p


def _read_registry_unlocked() -> dict[str, Any]:
    p = _registry_path()
    if not p.exists():
        return {"version": 1, "current_project": "default", "projects": ["default"], "updated_at": float(time.time())}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "current_project": "default", "projects": ["default"], "updated_at": float(time.time())}
    if not isinstance(raw, dict):
        return {"version": 1, "current_project": "default", "projects": ["default"], "updated_at": float(time.time())}
    projects = raw.get("projects", [])
    if not isinstance(projects, list):
        projects = []
    normalized = [str(x).strip() for x in projects if str(x).strip()]
    if "default" not in normalized:
        normalized.insert(0, "default")
    current = str(raw.get("current_project", "default") or "default").strip() or "default"
    if current not in normalized:
        current = normalized[0] if normalized else "default"
    return {
        "version": 1,
        "current_project": current,
        "projects": sorted(set(normalized)),
        "updated_at": float(raw.get("updated_at", time.time()) or time.time()),
    }


def _write_registry_unlocked(data: dict[str, Any]) -> dict[str, Any]:
    projects = [str(x).strip() for x in list(data.get("projects", []) or []) if str(x).strip()]
    if "default" not in projects:
        projects.insert(0, "default")
    projects = sorted(set(projects))
    current = str(data.get("current_project", "default") or "default").strip() or "default"
    if current not in projects:
        current = projects[0]
    payload = {
        "version": 1,
        "current_project": current,
        "projects": projects,
        "updated_at": float(time.time()),
    }
    _registry_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def with_lock(mutator):
    lp = _lock_path()
    with lp.open("r+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            cur = _read_registry_unlocked()
            nxt = mutator(dict(cur or {}))
            return _write_registry_unlocked(nxt if isinstance(nxt, dict) else cur)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def ensure_registry(project_ids: Iterable[str], current_project: str = "default") -> dict[str, Any]:
    want = sorted({str(x).strip() for x in list(project_ids or []) if str(x).strip()})
    if "default" not in want:
        want.insert(0, "default")

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        return {
            **cur,
            "projects": want,
            "current_project": str(cur.get("current_project", current_project) or current_project),
        }

    out = with_lock(_mut)
    # ensure current pointer remains valid against latest list
    if out["current_project"] not in set(out["projects"]):
        out = set_current_project(current_project if current_project in set(out["projects"]) else out["projects"][0])
    return out


def snapshot() -> dict[str, Any]:
    def _id(cur: dict[str, Any]) -> dict[str, Any]:
        return cur

    return with_lock(_id)


def current_project(default: str = "default") -> str:
    row = snapshot()
    cur = str(row.get("current_project", default) or default).strip() or default
    return cur


def set_current_project(project_id: str) -> dict[str, Any]:
    pid = str(project_id or "").strip()
    if not pid:
        raise ValueError("project_id is required")

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        projects = list(cur.get("projects", []) or [])
        if pid not in projects:
            raise ValueError(f"project '{pid}' not found in registry")
        cur["current_project"] = pid
        return cur

    return with_lock(_mut)


def add_project(project_id: str) -> dict[str, Any]:
    pid = str(project_id or "").strip()
    if not pid:
        raise ValueError("project_id is required")

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        projects = set(str(x).strip() for x in list(cur.get("projects", []) or []) if str(x).strip())
        projects.add(pid)
        cur["projects"] = sorted(projects)
        if not str(cur.get("current_project", "")).strip():
            cur["current_project"] = pid
        return cur

    return with_lock(_mut)


def remove_project(project_id: str) -> dict[str, Any]:
    pid = str(project_id or "").strip()
    if not pid:
        raise ValueError("project_id is required")
    if pid == "default":
        raise ValueError("cannot remove default project")

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        projects = [x for x in list(cur.get("projects", []) or []) if str(x).strip() and str(x).strip() != pid]
        if "default" not in projects:
            projects.append("default")
        projects = sorted(set(projects))
        cur["projects"] = projects
        if str(cur.get("current_project", "")).strip() == pid:
            cur["current_project"] = "default"
        return cur

    return with_lock(_mut)

