"""Per-project agent registry (entity membership + active flag)."""
from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path
from typing import Any, Iterable

from gods.identity import is_valid_agent_id
from gods.paths import agent_dir, project_dir, runtime_dir, runtime_locks_dir


def _registry_path(project_id: str) -> Path:
    p = runtime_dir(project_id) / "agent_registry.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _lock_path(project_id: str) -> Path:
    p = runtime_locks_dir(project_id) / "agent_registry.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch(exist_ok=True)
    return p


def _fs_agents(project_id: str) -> list[str]:
    base = project_dir(project_id) / "agents"
    if not base.exists():
        return []
    out: list[str] = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        aid = str(d.name or "").strip()
        if is_valid_agent_id(aid):
            out.append(aid)
    return sorted(set(out))


def _read_unlocked(project_id: str) -> dict[str, Any]:
    p = _registry_path(project_id)
    if not p.exists():
        return {"version": 1, "project_id": project_id, "agents": {}, "updated_at": float(time.time())}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "project_id": project_id, "agents": {}, "updated_at": float(time.time())}
    if not isinstance(raw, dict):
        return {"version": 1, "project_id": project_id, "agents": {}, "updated_at": float(time.time())}
    agents = raw.get("agents", {})
    if not isinstance(agents, dict):
        agents = {}
    normalized: dict[str, dict[str, Any]] = {}
    for aid, row in agents.items():
        a = str(aid or "").strip()
        if not is_valid_agent_id(a):
            continue
        r = row if isinstance(row, dict) else {}
        normalized[a] = {
            "active": bool(r.get("active", False)),
            "created_at": float(r.get("created_at", time.time()) or time.time()),
            "updated_at": float(r.get("updated_at", time.time()) or time.time()),
        }
    return {
        "version": 1,
        "project_id": project_id,
        "agents": normalized,
        "updated_at": float(raw.get("updated_at", time.time()) or time.time()),
    }


def _write_unlocked(project_id: str, data: dict[str, Any]) -> dict[str, Any]:
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        agents = {}
    normalized: dict[str, dict[str, Any]] = {}
    now = float(time.time())
    for aid, row in agents.items():
        a = str(aid or "").strip()
        if not is_valid_agent_id(a):
            continue
        r = row if isinstance(row, dict) else {}
        normalized[a] = {
            "active": bool(r.get("active", False)),
            "created_at": float(r.get("created_at", now) or now),
            "updated_at": float(r.get("updated_at", now) or now),
        }
    payload = {
        "version": 1,
        "project_id": project_id,
        "agents": normalized,
        "updated_at": now,
    }
    _registry_path(project_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def with_lock(project_id: str, mutator):
    lp = _lock_path(project_id)
    with lp.open("r+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            cur = _read_unlocked(project_id)
            nxt = mutator(dict(cur or {}))
            return _write_unlocked(project_id, nxt if isinstance(nxt, dict) else cur)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def ensure_registry(project_id: str, *, legacy_active_agents: Iterable[str] | None = None) -> dict[str, Any]:
    fs_agents = set(_fs_agents(project_id))
    legacy = {str(x).strip() for x in list(legacy_active_agents or []) if is_valid_agent_id(str(x).strip())}

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        agents = cur.get("agents", {})
        if not isinstance(agents, dict):
            agents = {}
        now = float(time.time())
        # Ensure all fs agents exist.
        for aid in fs_agents:
            row = agents.get(aid, {})
            if not isinstance(row, dict):
                row = {}
            agents[aid] = {
                "active": bool(row.get("active", False)),
                "created_at": float(row.get("created_at", now) or now),
                "updated_at": now,
            }
        # One-time migration path for legacy active list.
        for aid in legacy:
            row = agents.get(aid, {})
            if not isinstance(row, dict):
                row = {}
            agents[aid] = {
                "active": True,
                "created_at": float(row.get("created_at", now) or now),
                "updated_at": now,
            }
        # Prune missing entities to enforce zero-compat registry truth.
        stale = [aid for aid in agents.keys() if aid not in fs_agents]
        for aid in stale:
            agents.pop(aid, None)
        cur["agents"] = agents
        return cur

    return with_lock(project_id, _mut)


def list_agents(project_id: str, *, active_only: bool = False) -> list[str]:
    row = ensure_registry(project_id)
    out: list[str] = []
    for aid, meta in (row.get("agents", {}) or {}).items():
        if active_only and not bool((meta or {}).get("active", False)):
            continue
        out.append(str(aid))
    return sorted(set(out))


def list_active_agents(project_id: str) -> list[str]:
    return list_agents(project_id, active_only=True)


def is_active(project_id: str, agent_id: str) -> bool:
    aid = str(agent_id or "").strip()
    if not is_valid_agent_id(aid):
        return False
    row = ensure_registry(project_id)
    meta = (row.get("agents", {}) or {}).get(aid)
    return bool((meta or {}).get("active", False))


def register_agent(project_id: str, agent_id: str, *, active: bool = False) -> dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not is_valid_agent_id(aid):
        raise ValueError(f"invalid agent_id: {aid}")
    if not agent_dir(project_id, aid).exists():
        raise ValueError(f"agent entity not found: {project_id}/{aid}")

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        agents = cur.get("agents", {})
        if not isinstance(agents, dict):
            agents = {}
        now = float(time.time())
        row = agents.get(aid, {})
        if not isinstance(row, dict):
            row = {}
        agents[aid] = {
            "active": bool(active if "active" not in row else bool(row.get("active", False) or active)),
            "created_at": float(row.get("created_at", now) or now),
            "updated_at": now,
        }
        cur["agents"] = agents
        return cur

    return with_lock(project_id, _mut)


def unregister_agent(project_id: str, agent_id: str) -> dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not aid:
        return ensure_registry(project_id)

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        agents = cur.get("agents", {})
        if isinstance(agents, dict):
            agents.pop(aid, None)
            cur["agents"] = agents
        return cur

    return with_lock(project_id, _mut)


def set_active(project_id: str, agent_id: str, active: bool) -> dict[str, Any]:
    aid = str(agent_id or "").strip()
    if not is_valid_agent_id(aid):
        raise ValueError(f"invalid agent_id: {aid}")

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        agents = cur.get("agents", {})
        if not isinstance(agents, dict):
            agents = {}
        if aid not in agents:
            raise ValueError(f"agent '{aid}' not registered in project '{project_id}'")
        row = agents.get(aid, {})
        if not isinstance(row, dict):
            row = {}
        now = float(time.time())
        row["active"] = bool(active)
        row["updated_at"] = now
        row["created_at"] = float(row.get("created_at", now) or now)
        agents[aid] = row
        cur["agents"] = agents
        return cur

    return with_lock(project_id, _mut)


def replace_active_agents(project_id: str, agent_ids: Iterable[str]) -> dict[str, Any]:
    want = {str(x).strip() for x in list(agent_ids or []) if is_valid_agent_id(str(x).strip())}

    def _mut(cur: dict[str, Any]) -> dict[str, Any]:
        agents = cur.get("agents", {})
        if not isinstance(agents, dict):
            agents = {}
        now = float(time.time())
        for aid, row in list(agents.items()):
            r = row if isinstance(row, dict) else {}
            r["active"] = aid in want
            r["updated_at"] = now
            r["created_at"] = float(r.get("created_at", now) or now)
            agents[aid] = r
        cur["agents"] = agents
        return cur

    return with_lock(project_id, _mut)

