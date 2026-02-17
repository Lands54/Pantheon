from __future__ import annotations

import json
from pathlib import Path

import pytest

from gods.config import SystemConfig


def test_config_rejects_legacy_phase_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = {
        "openrouter_api_key": "",
        "current_project": "default",
        "projects": {
            "default": {
                "phase_strategy": "react_graph",
                "phase_mode" + "_enabled": True,
            }
        },
    }
    Path("config.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(RuntimeError):
        SystemConfig.load()
