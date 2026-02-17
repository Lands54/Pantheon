import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str):
    return subprocess.run(
        [sys.executable, "cli/main.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_removed_commands_not_available():
    for cmd in ["broadcast", "prayers", "pulse"]:
        r = _run(cmd)
        assert r.returncode != 0
        assert "invalid choice" in (r.stderr or "") or "usage" in (r.stderr or "").lower()


def test_inbox_events_subcommand_removed():
    r = _run("inbox", "events")
    assert r.returncode != 0
    assert "invalid choice" in (r.stderr or "")
