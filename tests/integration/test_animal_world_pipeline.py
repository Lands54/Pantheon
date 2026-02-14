import json
import shutil
from pathlib import Path

from gods.config import runtime_config
from scripts.run_animal_world_demo import main as run_animal_world


def test_animal_world_pipeline_generates_outputs():
    config_path = Path("config.json")
    old_config = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    old_current = runtime_config.current_project
    had_project = "animal_world" in runtime_config.projects

    try:
        run_animal_world()
        report = Path("projects/animal_world/agents/ground/animal_world_output.json")
        graph = Path("projects/animal_world/knowledge/knowledge_graph.json")
        proto = Path("projects/animal_world/protocols/events.jsonl")

        assert report.exists()
        assert graph.exists()
        assert proto.exists()

        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["final_state"]["sheep"] > 0
        assert data["final_state"]["grass"] > 0
    finally:
        runtime_config.current_project = old_current
        runtime_config.save()
        if not had_project and "animal_world" in runtime_config.projects:
            del runtime_config.projects["animal_world"]
            runtime_config.save()
        if Path("projects/animal_world").exists():
            shutil.rmtree("projects/animal_world")
        if old_config:
            config_path.write_text(old_config, encoding="utf-8")
