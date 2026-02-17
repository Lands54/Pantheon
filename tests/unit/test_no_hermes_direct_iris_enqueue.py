from pathlib import Path


def test_no_hermes_direct_iris_enqueue_import():
    root = Path(__file__).resolve().parents[2]
    for p in (root / "gods" / "hermes").rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        assert "from gods.iris.facade import enqueue_message" not in text

