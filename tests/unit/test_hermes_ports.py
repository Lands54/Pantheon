from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from gods.hermes.facade import HermesPortRegistry


def test_hermes_ports_reserve_list_release():
    project_id = f"ports_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        mgr = HermesPortRegistry()
        lease = mgr.reserve(project_id, owner_id="grass", min_port=15000, max_port=15100, note="grass api")
        assert int(lease["port"]) >= 15000

        rows = mgr.list(project_id)
        assert any(r.get("owner_id") == "grass" for r in rows)

        released = mgr.release(project_id, owner_id="grass", port=int(lease["port"]))
        assert released == 1
    finally:
        if base.exists():
            shutil.rmtree(base)
