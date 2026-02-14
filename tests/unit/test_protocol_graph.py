import json
import shutil
import uuid
from pathlib import Path

from gods.protocols.graph import build_knowledge_graph


def test_build_knowledge_graph_from_events():
    project_id = f"kg_test_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    proto_dir = base / "protocols"
    proto_dir.mkdir(parents=True, exist_ok=True)
    event_file = proto_dir / "events.jsonl"

    rows = [
        {
            "protocol_id": "p1",
            "subject": "sheep",
            "topic": "生态平衡协议",
            "relation": "consumes",
            "object": "grass",
            "clause": "limit grazing",
            "status": "agreed",
        },
        {
            "protocol_id": "p2",
            "subject": "tiger",
            "topic": "生态平衡协议",
            "relation": "preys_on",
            "object": "sheep",
            "clause": "avoid overhunting",
            "status": "agreed",
        },
    ]
    with event_file.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    graph = build_knowledge_graph(project_id)
    assert graph["project_id"] == project_id
    assert len(graph["nodes"]) >= 4
    assert len(graph["edges"]) >= 2

    out = base / "knowledge" / "knowledge_graph.json"
    assert out.exists()

    shutil.rmtree(base)
