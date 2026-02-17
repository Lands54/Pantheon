from __future__ import annotations

import json
from pathlib import Path

import pytest

from gods.config import SystemConfig


def test_load_rejects_legacy_config_payload(tmp_path, monkeypatch):
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

    with pytest.raises(RuntimeError):
        SystemConfig.load()


def test_load_rejects_legacy_phase_fields_and_invalid_phase_strategy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = {
        "openrouter_api_key": "",
        "current_project": "default",
        "projects": {
            "default": {
                "command_executor": "bad_executor",
                "context_strategy": "bad_strategy",
                "phase_strategy": "wrong_phase",
                "phase_mode" + "_enabled": True,
                "context_token_budget_total": 10,
                "command_timeout_sec": 0,
            }
        },
    }
    Path("config.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(RuntimeError):
        SystemConfig.load()
