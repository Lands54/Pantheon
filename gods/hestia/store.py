"""Hestia social graph store (adjacency matrix)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from gods.config import runtime_config
from gods.identity import is_valid_agent_id
from gods.paths import project_dir


_GRAPH_VERSION = 1


def _graph_path(project_id: str) -> Path:
    p = project_dir(project_id) / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p / "hestia_social_graph.json"


def _list_project_agents(project_id: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    proj = runtime_config.projects.get(project_id)
    if proj is not None:
        for aid in list(getattr(proj, "active_agents", []) or []):
            aa = str(aid or "").strip()
            if not is_valid_agent_id(aa) or aa in seen:
                continue
            seen.add(aa)
            out.append(aa)
        for aid in list(getattr(proj, "agent_settings", {}).keys() or []):
            aa = str(aid or "").strip()
            if not is_valid_agent_id(aa) or aa in seen:
                continue
            seen.add(aa)
            out.append(aa)

    agents_root = project_dir(project_id) / "agents"
    if not agents_root.exists():
        return sorted(out)
    for row in sorted(agents_root.iterdir(), key=lambda x: x.name):
        if not row.is_dir():
            continue
        aid = str(row.name)
        if not is_valid_agent_id(aid):
            continue
        if aid in seen:
            continue
        seen.add(aid)
        out.append(aid)
    return sorted(out)


def _default_matrix(nodes: list[str]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for src in nodes:
        row: dict[str, int] = {}
        for dst in nodes:
            row[dst] = 0 if src == dst else 1
        matrix[src] = row
    return matrix


def _normalize_matrix(nodes: list[str], matrix: dict) -> dict[str, dict[str, int]]:
    node_set = set(nodes)
    out: dict[str, dict[str, int]] = {}
    for src in nodes:
        src_raw = matrix.get(src, {}) if isinstance(matrix, dict) else {}
        row: dict[str, int] = {}
        for dst in nodes:
            if src == dst:
                row[dst] = 0
                continue
            val = 0
            if isinstance(src_raw, dict):
                raw = src_raw.get(dst, 0)
                val = 1 if int(raw) > 0 else 0
            row[dst] = val
        out[src] = row

    # keep any matrix keys that are in nodes but were strings with extra spaces, etc. impossible now
    # all unknown nodes are dropped by design.
    _ = node_set
    return out


def load_graph(project_id: str) -> dict:
    gp = _graph_path(project_id)
    nodes = _list_project_agents(project_id)
    if not gp.exists():
        payload = {
            "version": _GRAPH_VERSION,
            "project_id": project_id,
            "nodes": nodes,
            "matrix": _default_matrix(nodes),
            "updated_at": time.time(),
        }
        save_graph(project_id, payload)
        return payload

    try:
        raw = json.loads(gp.read_text(encoding="utf-8"))
    except Exception:
        raw = {}

    matrix = raw.get("matrix", {}) if isinstance(raw, dict) else {}
    normalized = {
        "version": _GRAPH_VERSION,
        "project_id": project_id,
        "nodes": nodes,
        "matrix": _normalize_matrix(nodes, matrix),
        "updated_at": float(raw.get("updated_at", time.time())) if isinstance(raw, dict) else time.time(),
    }

    # Keep graph always in sync with current agent set.
    save_graph(project_id, normalized)
    return normalized


def save_graph(project_id: str, graph: dict) -> dict:
    gp = _graph_path(project_id)
    nodes = [str(x) for x in list(graph.get("nodes", [])) if is_valid_agent_id(str(x))]
    nodes = sorted(list(dict.fromkeys(nodes)))
    matrix = _normalize_matrix(nodes, graph.get("matrix", {}))
    payload = {
        "version": _GRAPH_VERSION,
        "project_id": project_id,
        "nodes": nodes,
        "matrix": matrix,
        "updated_at": time.time(),
    }
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def set_edge(project_id: str, from_id: str, to_id: str, allowed: bool) -> dict:
    g = load_graph(project_id)
    nodes = list(g.get("nodes", []))
    if from_id not in nodes or to_id not in nodes:
        raise ValueError("from_id/to_id must exist in project agents")
    if from_id == to_id:
        raise ValueError("self edge is not allowed")
    g["matrix"][from_id][to_id] = 1 if bool(allowed) else 0
    return save_graph(project_id, g)


def replace_graph(project_id: str, nodes: list[str], matrix: dict) -> dict:
    filtered = [str(x).strip() for x in list(nodes or []) if is_valid_agent_id(str(x).strip())]
    filtered = sorted(list(dict.fromkeys(filtered)))
    return save_graph(project_id, {"nodes": filtered, "matrix": matrix})
