"""
Build project-level knowledge graph from protocol events.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _node_id(kind: str, value: str) -> str:
    return f"{kind}:{value}"


def build_knowledge_graph(project_id: str) -> dict:
    """
    Build and persist a property graph JSON from protocol events.
    Graph output: projects/{project_id}/knowledge/knowledge_graph.json
    """
    project_root = Path("projects") / project_id
    protocol_file = project_root / "protocols" / "events.jsonl"
    events = _load_jsonl(protocol_file)

    nodes = {}
    edges = []

    def upsert_node(node_id: str, kind: str, label: str):
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "kind": kind, "label": label}

    for event in events:
        if event.get("status") not in {"agreed", "active"}:
            continue

        subject = str(event.get("subject", "")).strip()
        relation = str(event.get("relation", "")).strip()
        obj = str(event.get("object", "")).strip()
        topic = str(event.get("topic", "")).strip()
        protocol_id = str(event.get("protocol_id", "")).strip()
        clause = str(event.get("clause", "")).strip()

        if not (subject and relation and obj):
            continue

        s_id = _node_id("agent", subject)
        o_id = _node_id("entity", obj)
        upsert_node(s_id, "agent", subject)
        upsert_node(o_id, "entity", obj)

        topic_id = ""
        if topic:
            topic_id = _node_id("topic", topic)
            upsert_node(topic_id, "topic", topic)

        edge = {
            "source": s_id,
            "target": o_id,
            "relation": relation,
            "protocol_id": protocol_id,
            "topic": topic,
            "clause": clause,
        }
        edges.append(edge)

        if topic_id:
            edges.append(
                {
                    "source": s_id,
                    "target": topic_id,
                    "relation": "negotiates",
                    "protocol_id": protocol_id,
                    "topic": topic,
                    "clause": clause,
                }
            )

    graph = {
        "project_id": project_id,
        "generated_at": int(time.time()),
        "nodes": list(nodes.values()),
        "edges": edges,
        "source_event_count": len(events),
        "active_edge_count": len(edges),
    }

    out_dir = project_root / "knowledge"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "knowledge_graph.json"
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return graph
