from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from gods.project.reporting import build_project_report, load_project_report


def test_build_project_report_empty_project():
    project_id = f"project_report_empty_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        report = build_project_report(project_id)
        assert report["project_id"] == project_id
        assert report["protocol_count"] == 0
        assert report["invocation_count"] == 0
        assert Path(report["output"]["json"]).exists()
        assert Path(report["output"]["md"]).exists()
        assert Path(report["output"]["mirror_md"]).exists()

        loaded = load_project_report(project_id)
        assert loaded is not None
        assert loaded["project_id"] == project_id
    finally:
        if base.exists():
            shutil.rmtree(base)
        mirror = Path("reports") / f"project_{project_id}_latest.md"
        if mirror.exists():
            mirror.unlink()


def test_build_project_report_with_data():
    project_id = f"project_report_data_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        protocols_dir = base / "protocols"
        protocols_dir.mkdir(parents=True, exist_ok=True)
        (protocols_dir / "registry.json").write_text(
            json.dumps({"protocols": [{"name": "grass.grow"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (protocols_dir / "contracts.json").write_text(
            json.dumps({"contracts": [{"title": "Eco Contract", "version": "1.0.0"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (protocols_dir / "invocations.jsonl").write_text(
            "\n".join(
                [
                    json.dumps({"name": "grass.grow", "status": "succeeded", "caller_id": "ground"}),
                    json.dumps({"name": "grass.grow", "status": "failed", "caller_id": "ground"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        runtime_dir = base / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "ports.json").write_text(
            json.dumps({"leases": [{"owner_id": "grass_api", "port": 18080}]}, ensure_ascii=False),
            encoding="utf-8",
        )

        report = build_project_report(project_id)
        assert report["protocol_count"] == 1
        assert report["contract_count"] == 1
        assert report["invocation_count"] == 2
        assert report["status_summary"]["succeeded"] == 1
        assert report["status_summary"]["failed"] == 1
        assert report["port_leases_summary"]["lease_count"] == 1
        assert report["top_protocols"][0]["protocol"] == "grass.grow"
        assert report["top_callers"][0]["caller_id"] == "ground"
        assert report.get("mnemosyne_entry_id")
    finally:
        if base.exists():
            shutil.rmtree(base)
        mirror = Path("reports") / f"project_{project_id}_latest.md"
        if mirror.exists():
            mirror.unlink()
