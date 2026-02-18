from __future__ import annotations

from pathlib import Path


def test_artifact_storage_path_not_directly_used_outside_mnemosyne_artifacts():
    repo = Path(__file__).resolve().parents[2]
    allowed = {
        "gods/mnemosyne/artifacts.py",
    }
    hits: list[str] = []
    for p in (repo / "gods").rglob("*.py"):
        rel = p.relative_to(repo).as_posix()
        if rel in allowed:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "mnemosyne/artifacts" in text or "artifacts/blobs" in text:
            hits.append(rel)
    assert not hits, f"artifact storage path access must go through mnemosyne facade: {hits}"

