from __future__ import annotations

from pathlib import Path

from gods.config.runtime import get_available_agents
from gods.identity import HUMAN_AGENT_ID, is_valid_agent_id


def test_agent_id_validation_rules():
    assert is_valid_agent_id("genesis") is True
    assert is_valid_agent_id("ground_1") is True
    assert is_valid_agent_id("High Overseer") is False
    assert is_valid_agent_id("hign overseer") is False
    assert is_valid_agent_id(HUMAN_AGENT_ID) is False
    assert is_valid_agent_id("") is False


def test_get_available_agents_filters_invalid_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agents_dir = Path("projects") / "default" / "agents"
    (agents_dir / "genesis").mkdir(parents=True, exist_ok=True)
    (agents_dir / "hign overseer").mkdir(parents=True, exist_ok=True)
    (agents_dir / ".hidden").mkdir(parents=True, exist_ok=True)
    out = sorted(get_available_agents("default"))
    assert out == ["genesis"]
