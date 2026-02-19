from __future__ import annotations

import shutil
from pathlib import Path

from gods.hestia import facade as hestia_facade


def test_hestia_creates_full_mesh_file_when_missing():
    project_id = "unit_hestia_autocreate_file"
    base = Path("projects") / project_id
    graph_path = base / "runtime" / "hestia_social_graph.json"
    shutil.rmtree(base, ignore_errors=True)
    try:
        (base / "agents" / "a").mkdir(parents=True, exist_ok=True)
        (base / "agents" / "b").mkdir(parents=True, exist_ok=True)
        assert not graph_path.exists()

        graph = hestia_facade.get_social_graph(project_id)
        assert graph_path.exists()
        assert int(graph["matrix"]["a"]["b"]) == 1
        assert int(graph["matrix"]["b"]["a"]) == 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_hestia_default_full_mesh_and_edge_update():
    project_id = "unit_hestia_graph"
    base = Path("projects") / project_id
    shutil.rmtree(base, ignore_errors=True)
    try:
        (base / "agents" / "alice").mkdir(parents=True, exist_ok=True)
        (base / "agents" / "bob").mkdir(parents=True, exist_ok=True)

        graph = hestia_facade.get_social_graph(project_id)
        assert set(graph.get("nodes", [])) == {"alice", "bob"}
        assert int(graph["matrix"]["alice"]["bob"]) == 1

        updated = hestia_facade.set_social_edge(project_id, "alice", "bob", False)
        assert int(updated["matrix"]["alice"]["bob"]) == 0
        assert hestia_facade.can_message(project_id, "alice", "bob") is False
        assert hestia_facade.can_message(project_id, "bob", "alice") is True
    finally:
        shutil.rmtree(base, ignore_errors=True)
