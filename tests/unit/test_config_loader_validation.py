from __future__ import annotations

import json
from pathlib import Path

from gods.config import SystemConfig


def test_load_migrates_legacy_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy = {
        "openrouter_api_key": "k1",
        "active_agents": ["a"],
        "agent_settings": {"a": {"model": "m1"}},
        "simulation_enabled": True,
        "simulation_interval_min": 12,
        "simulation_interval_max": 33,
    }
    Path("config.json").write_text(json.dumps(legacy), encoding="utf-8")

    cfg = SystemConfig.load()
    assert cfg.current_project == "default"
    assert "default" in cfg.projects
    assert cfg.projects["default"].active_agents == ["a"]
    assert cfg.projects["default"].agent_settings["a"].model == "m1"


def test_load_normalizes_invalid_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = {
        "openrouter_api_key": "",
        "current_project": "default",
        "projects": {
            "default": {
                "command_executor": "bad_executor",
                "context_strategy": "bad_strategy",
                "phase_strategy": "wrong_phase",
                "context_token_budget_total": 10,
                "command_timeout_sec": 0,
            }
        },
    }
    Path("config.json").write_text(json.dumps(raw), encoding="utf-8")

    cfg = SystemConfig.load()
    proj = cfg.projects["default"]
    assert proj.command_executor == "local"
    assert proj.context_strategy == "structured_v1"
    assert proj.phase_strategy == "strict_triad"
    assert proj.context_token_budget_total >= 4000
    assert proj.command_timeout_sec >= 1
