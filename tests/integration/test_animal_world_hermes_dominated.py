from __future__ import annotations

import json
from pathlib import Path

from scripts.run_animal_world_hermes import run_demo


def test_animal_world_hermes_dominated_run():
    summary = run_demo(project_id="animal_world_hermes_test", steps=20, seed=7)
    assert summary["project_id"] == "animal_world_hermes_test"
    assert summary["route_invocation_count"] >= 80  # 4 routes per step
    final_state = summary["final_state"]
    assert final_state["sheep"] > 0
    assert final_state["grass"] > 0

    out_file = Path("reports") / "animal_world_hermes_run" / "summary.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["project_id"] == "animal_world_hermes_test"
    assert "resolved_contract" in data
