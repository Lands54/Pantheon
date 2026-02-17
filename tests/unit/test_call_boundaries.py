from __future__ import annotations

import subprocess
from pathlib import Path


def test_call_boundaries_are_zero():
    repo = Path(__file__).resolve().parents[2]
    script = repo / "scripts" / "check_call_boundaries.py"
    res = subprocess.run(
        ["python", str(script)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"call boundary violations detected:\n{res.stdout}\n{res.stderr}"
    assert "CALL_BOUNDARY_VIOLATION_COUNT 0" in res.stdout
