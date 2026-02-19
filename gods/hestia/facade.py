"""Hestia facade: social graph read/write and route checks."""
from __future__ import annotations

from gods.identity import HUMAN_AGENT_ID, is_valid_agent_id

from . import store


def get_social_graph(project_id: str) -> dict:
    return store.load_graph(project_id)


def set_social_edge(project_id: str, from_id: str, to_id: str, allowed: bool) -> dict:
    return store.set_edge(project_id, from_id, to_id, allowed)


def replace_social_graph(project_id: str, nodes: list[str], matrix: dict) -> dict:
    return store.replace_graph(project_id, nodes, matrix)


def list_reachable_agents(project_id: str, caller_id: str) -> list[str]:
    g = store.load_graph(project_id)
    nodes = list(g.get("nodes", []))
    caller = str(caller_id or "").strip()

    # Human/system callers can inspect full graph.
    if caller in {"", HUMAN_AGENT_ID, "external", "system"} or not is_valid_agent_id(caller):
        return nodes

    if caller not in nodes:
        return []

    row = (g.get("matrix", {}) or {}).get(caller, {})
    out: list[str] = []
    for aid in nodes:
        if aid == caller:
            continue
        try:
            if int((row or {}).get(aid, 0)) > 0:
                out.append(aid)
        except Exception:
            continue
    return out


def can_message(project_id: str, from_id: str, to_id: str) -> bool:
    src = str(from_id or "").strip()
    dst = str(to_id or "").strip()
    if not dst:
        return False

    # Human/system callers bypass social graph restriction.
    if src in {"", HUMAN_AGENT_ID, "external", "system"} or not is_valid_agent_id(src):
        return True

    g = store.load_graph(project_id)
    nodes = set(g.get("nodes", []))
    if src not in nodes or dst not in nodes:
        return False

    row = (g.get("matrix", {}) or {}).get(src, {})
    try:
        return int((row or {}).get(dst, 0)) > 0
    except Exception:
        return False
