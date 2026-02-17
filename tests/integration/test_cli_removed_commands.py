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


def test_removed_cli_commands_return_argparse_error():
    for cmd in ["broadcast", "prayers", "pulse"]:
        r = _run(cmd)
        assert r.returncode == 2
        assert "invalid choice" in (r.stderr or "")
