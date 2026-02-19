"""CLI project command handlers."""
from __future__ import annotations

import json
import requests

from cli.utils import get_base_url


def _print_protocol_validation_summary(data: dict):
    val = data.get("protocol_execution_validation", {}) or {}
    if not val:
        print("   Protocol Validation: (unavailable from server response)")
        print("   Hint: restart API server to load the latest report schema.")
        return
    summary = val.get("summary", {}) or {}
    status = str(summary.get("status", "unknown")).lower()
    icon = "✅" if status == "pass" else ("⚠️" if status == "warn" else "❌")
    print(f"   Protocol Validation: {icon} {status}")
    print(
        "   Structural OK: "
        f"{summary.get('structural_ok', False)} | "
        f"Invocations: {summary.get('has_invocations', False)} | "
        f"Dormant Clauses: {summary.get('dormant_clause_count', 0)} | "
        f"Unhealthy Services: {summary.get('unhealthy_service_count', 0)}"
    )

    issues: list[str] = []
    for item in (val.get("missing_registry") or [])[:5]:
        issues.append(f"missing registry: {item.get('function_id', '')}")
    for item in (val.get("registry_mismatch") or [])[:5]:
        issues.append(
            "registry mismatch: "
            f"{item.get('function_id', '')} "
            f"(contract={item.get('contract_provider', '')}, registry={item.get('registry_provider', '')})"
        )
    for item in (val.get("orphan_invocations") or [])[:5]:
        issues.append(f"orphan invocation: {item.get('name', '')}")
    for item in (val.get("dormant_clauses") or [])[:5]:
        issues.append(f"dormant clause: {item.get('function_id', '')}")
    for item in (val.get("unhealthy_services") or [])[:5]:
        issues.append(
            f"unhealthy service: {item.get('url', '')} "
            f"(status={item.get('status_code', 0)} error={item.get('error', '')})"
        )

    if issues:
        print("   Top Issues:")
        for line in issues[:5]:
            print(f"   - {line}")


def cmd_project(args):
    """Manage Projects."""
    base_url = get_base_url()
    if args.subcommand == "list":
        try:
            res = requests.get(f"{base_url}/config")
            data = res.json()
            print("\n🌍 SACRED WORLDS")
            current = data.get("current_project")
            for pid, _ in data["projects"].items():
                marker = "⭐" if pid == current else "  "
                print(f"{marker} {pid}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "create":
        try:
            payload = {"id": args.id}
            res = requests.post(f"{base_url}/projects/create", json=payload)
            if res.status_code == 200:
                print(f"✨ World '{args.id}' manifested.")
            else:
                print(f"❌ Failed: {res.json().get('error', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "delete":
        try:
            res = requests.delete(f"{base_url}/projects/{args.id}")
            if res.status_code == 200:
                print(f"🗑️  World '{args.id}' collapsed and removed from existence.")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "switch":
        try:
            res = requests.get(f"{base_url}/config")
            data = res.json()
            if args.id not in data["projects"]:
                print(f"❌ World '{args.id}' does not exist.")
                return
            data["current_project"] = args.id
            requests.post(f"{base_url}/config/save", json=data)
            print(f"🌌 Shifted consciousness to world: {args.id}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "graph":
        try:
            res = requests.post(f"{base_url}/projects/{args.id}/knowledge/rebuild")
            if res.status_code == 200:
                data = res.json()
                print(f"🧠 Knowledge graph rebuilt for '{args.id}'")
                print(f"   Nodes: {data.get('nodes', 0)}")
                print(f"   Edges: {data.get('edges', 0)}")
                print(f"   Output: {data.get('output')}")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "start":
        try:
            res = requests.post(f"{base_url}/projects/{args.id}/start")
            if res.status_code == 200:
                data = res.json()
                print(f"🟢 Project started: {data.get('project_id')}")
                print(f"   Current Project: {data.get('current_project')}")
            else:
                detail = res.json().get("detail", "Unknown error")
                if res.status_code == 503 and "Docker unavailable" in str(detail):
                    print(f"❌ Failed to start project '{args.id}': {detail}")
                    print("   Project has been auto-stopped for safety.")
                    print("   Suggested next steps:")
                    print("   1) Start Docker Desktop / docker daemon")
                    print(f"   2) Retry: ./temple.sh project start {args.id}")
                    print(f"   3) Or switch backend: ./temple.sh -p {args.id} config set command_executor local")
                else:
                    print(f"❌ Failed: {detail}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "stop":
        try:
            res = requests.post(f"{base_url}/projects/{args.id}/stop")
            if res.status_code == 200:
                data = res.json()
                print(f"🔴 Project stopped: {data.get('project_id')}")
                print(f"   Current Project: {data.get('current_project')}")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "report":
        try:
            # Build report writes both project-local artifacts and Mnemosyne human archive entry.
            res = requests.post(f"{base_url}/projects/{args.id}/report/build")
            if res.status_code == 200:
                data = res.json()
                print(f"🧾 Project report built: {data.get('project_id')}")
                output = data.get("output", {})
                print(f"   JSON: {output.get('json')}")
                print(f"   MD: {output.get('md')}")
                if output.get("mirror_md"):
                    print(f"   Mirror: {output.get('mirror_md')}")
                _print_protocol_validation_summary(data)
                print(f"   Mnemosyne Entry: {data.get('mnemosyne_entry_id')}")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "report-show":
        try:
            res = requests.get(f"{base_url}/projects/{args.id}/report")
            if res.status_code == 200:
                print(json.dumps(res.json(), ensure_ascii=False, indent=2))
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "social-graph":
        try:
            res = requests.get(f"{base_url}/hestia/graph", params={"project_id": args.id})
            if res.status_code == 200:
                print(json.dumps(res.json(), ensure_ascii=False, indent=2))
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "social-edge":
        try:
            payload = {
                "project_id": args.id,
                "from_id": args.from_id,
                "to_id": args.to_id,
                "allowed": str(args.allow).strip().lower() == "true",
            }
            res = requests.post(f"{base_url}/hestia/edge", json=payload)
            if res.status_code == 200:
                print(json.dumps(res.json(), ensure_ascii=False, indent=2))
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")
