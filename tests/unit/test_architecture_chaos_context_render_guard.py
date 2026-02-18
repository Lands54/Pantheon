from __future__ import annotations

from pathlib import Path


def test_only_chaos_uses_render_intents_for_llm_for_runtime_injection():
    repo = Path(__file__).resolve().parents[2]
    hits: list[Path] = []
    for p in (repo / "gods").rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "render_intents_for_llm(" in text:
            hits.append(p)
    allowed = {
        repo / "gods" / "chaos" / "snapshot.py",
        repo / "gods" / "mnemosyne" / "facade.py",
    }
    unexpected = [str(p) for p in hits if p not in allowed]
    assert not unexpected, f"unexpected render_intents_for_llm usage outside Chaos/facade: {unexpected}"

