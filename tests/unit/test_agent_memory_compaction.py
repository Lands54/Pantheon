from pathlib import Path
import shutil

from gods.agents.base import GodAgent
from gods.config import runtime_config, ProjectConfig


def test_agent_memory_compaction_rolls_old_content():
    project_id = "unit_memory_compact"
    agent_id = "tester"
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# tester\ncompact test", encoding="utf-8")

    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="unit compact",
        active_agents=[agent_id],
        simulation_enabled=False,
        memory_compact_trigger_chars=1500,
        memory_compact_keep_chars=500,
    )

    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        initial_mem = (Path("projects") / project_id / "mnemosyne" / "chronicles" / f"{agent_id}.md").read_text(encoding="utf-8")
        assert initial_mem.startswith("### SYSTEM_SEED")
        for i in range(180):
            agent._append_to_memory(f"entry {i}: " + ("x" * 180))

        mem_path = Path("projects") / project_id / "mnemosyne" / "chronicles" / f"{agent_id}.md"
        archive_path = Path("projects") / project_id / "mnemosyne" / "chronicles" / f"{agent_id}_archive.md"
        mem_text = mem_path.read_text(encoding="utf-8")

        assert "MEMORY_COMPACTED" in mem_text
        assert mem_text.startswith("### SYSTEM_SEED")
        assert archive_path.exists()
        assert archive_path.stat().st_size > 0
        assert mem_path.stat().st_size < 15000
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
