from __future__ import annotations

from pathlib import Path


def test_godagent_no_legacy_heavy_private_impl():
    path = Path(__file__).resolve().parents[2] / "gods" / "agents" / "base.py"
    text = path.read_text(encoding="utf-8")
    banned_tokens = [
        "def _load_directives(",
        "def _ensure_memory_seeded(",
        "def _merge_state_window_if_needed(",
        "def _persist_state_window(",
        "def _return_with_state_window(",
        "def _resolve_node_tool_allowlist(",
        "def _classify_tool_status(",
    ]
    hits = [token for token in banned_tokens if token in text]
    assert not hits, f"GodAgent should stay thin; found legacy implementations: {hits}"
