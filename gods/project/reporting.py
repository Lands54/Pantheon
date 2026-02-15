"""Project report builder (Project-first, no standalone experiment domain)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
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


def _to_function_id(owner: str, clause_id: str) -> str:
    owner = str(owner or "").strip()
    clause_id = str(clause_id or "").strip()
    if not owner or not clause_id:
        return ""
    return f"{owner}.{clause_id}"


def _extract_contract_clauses(contract_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for contract in contract_rows:
        title = str(contract.get("title", ""))
        version = str(contract.get("version", ""))
        obligations = contract.get("obligations", {}) or {}
        if not isinstance(obligations, dict):
            continue
        for owner, rows in obligations.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                provider = row.get("provider", {}) or {}
                clause_id = str(row.get("id", "")).strip()
                item = {
                    "title": title,
                    "version": version,
                    "owner_agent": str(owner),
                    "clause_id": clause_id,
                    "function_id": _to_function_id(str(owner), clause_id),
                    "provider_url": str(provider.get("url", "")),
                    "provider_method": str(provider.get("method", "POST")).upper(),
                }
                out.append(item)
    return out


def _index_registry(protocol_rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_fn: dict[str, dict[str, Any]] = {}
    by_url_method: dict[str, dict[str, Any]] = {}
    for row in protocol_rows:
        fn = str(row.get("function_id", "")).strip()
        if fn:
            by_fn[fn] = row
        provider = row.get("provider", {}) or {}
        url = str(provider.get("url", "")).strip()
        method = str(provider.get("method", "POST")).upper().strip()
        if url:
            by_url_method[f"{method} {url}"] = row
    return by_fn, by_url_method


def _function_id_candidates(function_id: str) -> set[str]:
    fn = str(function_id or "").strip()
    if not fn:
        return set()
    last = fn.split(".")[-1]
    compact = fn.replace(".", "_")
    return {
        fn,
        compact,
        f".{fn}",
        f".{compact}",
        f"_{last}",
        f".{last}",
    }


def _count_invocations_for_clause(invocations: list[dict[str, Any]], protocol_name: str, function_id: str) -> int:
    c = 0
    name_exact = str(protocol_name or "").strip()
    fn_tokens = _function_id_candidates(function_id)
    for row in invocations:
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        if name_exact and name == name_exact:
            c += 1
            continue
        if any(tok and tok in name for tok in fn_tokens):
            c += 1
    return c


def _host_health_url(raw_url: str) -> str | None:
    u = str(raw_url or "").strip()
    if not u:
        return None
    try:
        parsed = urllib.parse.urlparse(u)
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return None
    port = parsed.port
    netloc = f"{host}:{port}" if port else host
    return f"{parsed.scheme}://{netloc}/health"


def _http_health_check(url: str, timeout_sec: float = 1.5) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            code = int(getattr(resp, "status", 0) or 0)
            return {"url": url, "ok": 200 <= code < 300, "status_code": code, "error": ""}
    except urllib.error.HTTPError as e:
        return {"url": url, "ok": False, "status_code": int(getattr(e, "code", 0) or 0), "error": str(e)}
    except Exception as e:
        return {"url": url, "ok": False, "status_code": 0, "error": str(e)}


def _build_protocol_execution_validation(
    contract_rows: list[dict[str, Any]],
    protocol_rows: list[dict[str, Any]],
    invocation_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    clauses = _extract_contract_clauses(contract_rows)
    by_fn, by_url_method = _index_registry(protocol_rows)

    missing_registry: list[dict[str, Any]] = []
    registry_mismatch: list[dict[str, Any]] = []
    mapped: list[dict[str, Any]] = []

    for c in clauses:
        fn = c.get("function_id", "")
        key = f"{c.get('provider_method')} {c.get('provider_url')}".strip()
        matched = by_fn.get(str(fn)) or by_url_method.get(key)
        if not matched:
            missing_registry.append(
                {
                    "function_id": fn,
                    "owner_agent": c.get("owner_agent", ""),
                    "provider": key,
                }
            )
            continue
        provider = matched.get("provider", {}) or {}
        mkey = f"{str(provider.get('method', 'POST')).upper()} {str(provider.get('url', '')).strip()}"
        if key and mkey and key != mkey:
            registry_mismatch.append(
                {
                    "function_id": fn,
                    "contract_provider": key,
                    "registry_provider": mkey,
                    "protocol_name": matched.get("name", ""),
                }
            )
        mapped.append(
            {
                "function_id": fn,
                "protocol_name": str(matched.get("name", "")),
                "owner_agent": c.get("owner_agent", ""),
                "provider_url": c.get("provider_url", ""),
            }
        )

    orphan_invocations = []
    known_names = {str(x.get("name", "")) for x in protocol_rows}
    for row in invocation_rows:
        nm = str(row.get("name", ""))
        if nm and nm not in known_names:
            orphan_invocations.append({"name": nm, "status": str(row.get("status", ""))})

    invocation_coverage: list[dict[str, Any]] = []
    dormant = []
    for row in mapped:
        cnt = _count_invocations_for_clause(invocation_rows, row.get("protocol_name", ""), row.get("function_id", ""))
        item = {
            "function_id": row.get("function_id", ""),
            "protocol_name": row.get("protocol_name", ""),
            "count": cnt,
        }
        invocation_coverage.append(item)
        if cnt == 0:
            dormant.append(item)

    health_targets = sorted({u for u in [_host_health_url(x.get("provider_url", "")) for x in mapped] if u})
    health_checks = [_http_health_check(u) for u in health_targets]
    unhealthy = [x for x in health_checks if not x.get("ok")]

    expected_clauses = len(clauses)
    mapped_count = len(mapped)
    result = {
        "expected_clauses": expected_clauses,
        "mapped_registry_entries": mapped_count,
        "missing_registry": missing_registry,
        "registry_mismatch": registry_mismatch,
        "orphan_invocations": orphan_invocations,
        "invocation_coverage": invocation_coverage,
        "dormant_clauses": dormant,
        "service_health_checks": health_checks,
        "unhealthy_services": unhealthy,
    }
    structural_ok = not (missing_registry or registry_mismatch or orphan_invocations)
    has_invocations = len(invocation_rows) > 0
    has_dormant = len(dormant) > 0
    has_unhealthy = len(unhealthy) > 0
    if not structural_ok:
        status = "fail"
    elif has_unhealthy or (has_invocations and has_dormant) or not has_invocations:
        status = "warn"
    else:
        status = "pass"

    result["summary"] = {
        "ok": status == "pass",
        "status": status,
        "structural_ok": structural_ok,
        "has_invocations": has_invocations,
        "dormant_clause_count": len(dormant),
        "unhealthy_service_count": len(unhealthy),
    }
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
    lines.append("## Protocol Execution Validation")
    val = report.get("protocol_execution_validation", {}) or {}
    summary = val.get("summary", {}) or {}
    lines.append(f"- Validation Status: {summary.get('status', 'unknown')}")
    lines.append(f"- Structural OK: {summary.get('structural_ok', False)}")
    lines.append(f"- Clauses mapped: {val.get('mapped_registry_entries', 0)}/{val.get('expected_clauses', 0)}")
    lines.append(f"- Dormant clauses: {summary.get('dormant_clause_count', 0)}")
    lines.append(f"- Unhealthy services: {summary.get('unhealthy_service_count', 0)}")
    if val.get("missing_registry"):
        lines.append("- Missing registry mappings:")
        for item in val.get("missing_registry", [])[:10]:
            lines.append(f"  - {item.get('function_id')}: {item.get('provider')}")
    if val.get("registry_mismatch"):
        lines.append("- Registry/provider mismatches:")
        for item in val.get("registry_mismatch", [])[:10]:
            lines.append(
                "  - "
                + f"{item.get('function_id')}: contract={item.get('contract_provider')} "
                + f"registry={item.get('registry_provider')}"
            )
    if val.get("orphan_invocations"):
        lines.append("- Orphan invocations (name not in registry):")
        for item in val.get("orphan_invocations", [])[:10]:
            lines.append(f"  - {item.get('name')} [{item.get('status')}]")
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
    if val.get("missing_registry"):
        lines.append("- Risk: some contract clauses are not mapped to registry protocols.")
    if val.get("orphan_invocations"):
        lines.append("- Risk: invocation names exist that are absent from current registry.")
    if summary.get("unhealthy_service_count", 0) > 0:
        lines.append("- Risk: one or more protocol provider services failed /health checks.")
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
        "protocol_execution_validation": _build_protocol_execution_validation(
            contract_rows=contract_rows,
            protocol_rows=protocol_rows,
            invocation_rows=invocation_rows,
        ),
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
