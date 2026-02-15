"""Project report builder (Project-first, no standalone experiment domain)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gods.hermes import store as hermes_store
from gods.mnemosyne import write_entry

TOP_N = 10


def _project_dir(project_id: str) -> Path:
    return Path("projects") / project_id


def _reports_dir(project_id: str) -> Path:
    p = _project_dir(project_id) / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _count_by(items: list[dict[str, Any]], key: str, fallback: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in items:
        value = str(row.get(key, fallback))
        out[value] = out.get(value, 0) + 1
    return out


def _top_protocols(invocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_protocol: dict[str, int] = {}
    for row in invocations:
        name = str(row.get("name", "unknown"))
        k = name
        by_protocol[k] = by_protocol.get(k, 0) + 1
    sorted_rows = sorted(by_protocol.items(), key=lambda x: x[1], reverse=True)[:TOP_N]
    return [{"protocol": k, "count": v} for k, v in sorted_rows]


def _top_callers(invocations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_caller = _count_by(invocations, "caller_id", "unknown")
    sorted_rows = sorted(by_caller.items(), key=lambda x: x[1], reverse=True)[:TOP_N]
    return [{"caller_id": k, "count": v} for k, v in sorted_rows]


def _mnemosyne_summary(project_id: str) -> dict[str, int]:
    base = _project_dir(project_id) / "mnemosyne"
    result = {"human": 0, "agent": 0, "system": 0}
    for vault in ("human", "agent", "system"):
        idx = base / vault / "entries.jsonl"
        result[vault] = len(_load_jsonl(idx))
    return result


def _markdown_from_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Project Report: {report['project_id']}")
    lines.append("")
    lines.append("## Project Overview")
    lines.append(f"- Generated At: {report['generated_at']}")
    lines.append(f"- Protocol Count: {report['protocol_count']}")
    lines.append(f"- Contract Count: {report['contract_count']}")
    lines.append(f"- Invocation Count: {report['invocation_count']}")
    lines.append("")
    lines.append("## Hermes Protocol Snapshot")
    if report["top_protocols"]:
        for row in report["top_protocols"]:
            lines.append(f"- {row['protocol']}: {row['count']}")
    else:
        lines.append("- No protocol invocations yet")
    lines.append("")
    lines.append("## Invocation Health")
    if report["status_summary"]:
        for k, v in sorted(report["status_summary"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- No invocations")
    lines.append("")
    lines.append("## Contract Coverage")
    lines.append(f"- Registered contracts: {report['contract_count']}")
    lines.append("")
    lines.append("## Port Lease State")
    lease_count = int(report["port_leases_summary"].get("lease_count", 0))
    lines.append(f"- Active leases: {lease_count}")
    if report["port_leases_summary"].get("owners"):
        for owner, cnt in report["port_leases_summary"]["owners"].items():
            lines.append(f"- {owner}: {cnt}")
    lines.append("")
    lines.append("## Mnemosyne Archive Snapshot")
    mnemo = report["mnemosyne_summary"]
    lines.append(f"- human: {mnemo.get('human', 0)}")
    lines.append(f"- agent: {mnemo.get('agent', 0)}")
    lines.append(f"- system: {mnemo.get('system', 0)}")
    lines.append("")
    lines.append("## Risks & Suggested Next Checks")
    if report["invocation_count"] == 0:
        lines.append("- Risk: no protocol invocation data; run at least one protocol call.")
    if report["contract_count"] == 0:
        lines.append("- Risk: no contract registered; role obligations may drift.")
    if lease_count > 0:
        lines.append("- Check: verify active port leases still correspond to running services.")
    if report["invocation_count"] > 0 and not report["top_callers"]:
        lines.append("- Check: caller_id missing in invocation rows.")
    if len(lines) > 0 and lines[-1] == "## Risks & Suggested Next Checks":
        lines.append("- No immediate risks detected from available project data.")
    return "\n".join(lines) + "\n"


def build_project_report(project_id: str, write_mirror: bool = True) -> dict[str, Any]:
    # Report aggregates only project-local facts (protocol logs, contracts, runtime leases, archives).
    protocol_rows = hermes_store.load_registry(project_id).get("protocols", [])
    contract_rows = hermes_store.load_contracts(project_id).get("contracts", [])
    invocation_rows = _load_jsonl(hermes_store.invocations_path(project_id))
    port_leases = hermes_store.load_ports(project_id).get("leases", [])

    status_summary = _count_by(invocation_rows, "status", "unknown")
    owners = _count_by(port_leases, "owner_id", "unknown")

    report: dict[str, Any] = {
        "project_id": project_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "protocol_count": len(protocol_rows),
        "contract_count": len(contract_rows),
        "invocation_count": len(invocation_rows),
        "status_summary": status_summary,
        "top_protocols": _top_protocols(invocation_rows),
        "top_callers": _top_callers(invocation_rows),
        "port_leases_summary": {
            "lease_count": len(port_leases),
            "owners": owners,
        },
        "mnemosyne_summary": _mnemosyne_summary(project_id),
        "output": {},
    }

    reports_dir = _reports_dir(project_id)
    json_path = reports_dir / "project_report.json"
    md_path = reports_dir / "project_report.md"

    md_text = _markdown_from_report(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")

    output = {
        "json": str(json_path),
        "md": str(md_path),
    }
    if write_mirror:
        # Optional global mirror for quick human browsing across projects.
        mirror = Path("reports") / f"project_{project_id}_latest.md"
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(md_text, encoding="utf-8")
        output["mirror_md"] = str(mirror)

    report["output"] = output
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    entry = write_entry(
        project_id=project_id,
        vault="human",
        author="system",
        title=f"Project Report: {project_id}",
        content=md_text,
        tags=["project_report", project_id],
    )
    report["mnemosyne_entry_id"] = entry.get("entry_id", "")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def load_project_report(project_id: str) -> dict[str, Any] | None:
    p = _reports_dir(project_id) / "project_report.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
