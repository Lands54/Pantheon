from __future__ import annotations

from pathlib import Path


def test_janus_no_read_exports_in_facade_or_init():
    repo = Path(__file__).resolve().parents[2]
    targets = [
        repo / "gods" / "janus" / "facade.py",
        repo / "gods" / "janus" / "__init__.py",
        repo / "gods" / "janus" / "service.py",
    ]
    banned = (
        "context_preview",
        "context_reports",
        "latest_context_report",
        "list_context_reports",
        "list_observations",
        "read_profile",
        "read_task_state",
    )
    for p in targets:
        text = p.read_text(encoding="utf-8", errors="ignore")
        for token in banned:
            assert token not in text, f"janus read/export token '{token}' found in {p}"

