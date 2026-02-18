from __future__ import annotations

import shutil
from pathlib import Path

from gods.mnemosyne.facade import chronicle_path, ensure_agent_memory_seeded, load_agent_directives


def test_mnemosyne_profile_and_seed():
    project_id = "unit_mn_profile_seed"
    agent_id = "solo"
    root = Path("projects") / project_id
    shutil.rmtree(root, ignore_errors=True)
    try:
        profile = root / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text("# directives", encoding="utf-8")

        directives = load_agent_directives(project_id, agent_id)
        assert directives.strip() == "# directives"

        workspace = root / "agents" / agent_id
        ensure_agent_memory_seeded(project_id, agent_id, directives, workspace)
        cpath = chronicle_path(project_id, agent_id)
        first = cpath.read_text(encoding="utf-8")
        assert "SYSTEM_SEED" in first

        cpath.write_text("existing", encoding="utf-8")
        ensure_agent_memory_seeded(project_id, agent_id, directives, workspace)
        assert cpath.read_text(encoding="utf-8") == "existing"
    finally:
        shutil.rmtree(root, ignore_errors=True)
