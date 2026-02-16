from __future__ import annotations

import subprocess
from pathlib import Path


def test_gods_import_cycles_are_zero():
    repo = Path(__file__).resolve().parents[2]
    script = repo / "scripts" / "check_import_cycles.py"
    res = subprocess.run(
        ["python", str(script), "--root", "gods"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"import cycles detected:\n{res.stdout}\n{res.stderr}"
    assert "CYCLE_COUNT 0" in res.stdout
