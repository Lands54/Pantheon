from __future__ import annotations

from pathlib import Path


def test_no_phase_runtime_imports():
    root = Path(".")
    deny = "gods.agents." + "phase_runtime"
    for p in root.rglob("*.py"):
        if any(x in p.parts for x in {".git", ".pytest_cache", "__pycache__", "projects", "archives"}):
            continue
        if p.name == "test_no_phase_runtime_imports.py":
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        assert deny not in text, f"legacy import found in {p}"
