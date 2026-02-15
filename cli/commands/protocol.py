"""CLI Protocol Commands (Hermes bus)."""
from __future__ import annotations

import json
import requests

from cli.utils import get_base_url


def _current_project(base_url: str, project_arg: str | None) -> str:
    if project_arg:
        return project_arg
    res = requests.get(f"{base_url}/config", timeout=5)
    data = res.json()
    return data.get("current_project", "default")


def cmd_protocol(args):
    base_url = get_base_url()
    pid = _current_project(base_url, getattr(args, "project", None))
    cfg = requests.get(f"{base_url}/config", timeout=5).json()
    proj = (cfg.get("projects") or {}).get(pid, {})

    if args.subcommand == "list":
        res = requests.get(f"{base_url}/hermes/list", params={"project_id": pid}, timeout=10)
        data = res.json()
        rows = data.get("protocols", [])
        print(f"📡 Hermes Protocols - Project: {pid}")
        if not rows:
            print("(none)")
            return
        for row in rows:
            provider = row.get("provider", {})
            print(f"- {row.get('name')}@{row.get('version')} [{row.get('status')}]")
            ptype = provider.get("type", "agent_tool")
            if ptype == "http":
                print(f"  provider=http:{provider.get('method', 'POST')} {provider.get('url')}")
            else:
                print(f"  provider=agent_tool:{provider.get('agent_id')}.{provider.get('tool_name')}")

    elif args.subcommand == "register":
        print("⚠️ DEPRECATED: protocol register is kept for compatibility.")
        print("   Recommended flow: contract-register + executable clauses + contract-commit.")
        req_schema = json.loads(args.request_schema) if args.request_schema else {"type": "object"}
        resp_schema = json.loads(args.response_schema) if args.response_schema else {"type": "object", "required": ["result"], "properties": {"result": {"type": "string"}}}
        provider_type = args.provider
        if provider_type == "agent_tool":
            if not proj.get("hermes_allow_agent_tool_provider", False):
                print("❌ agent_tool provider is disabled by policy for this project. Use --provider http.")
                return
            if not args.agent or not args.tool:
                print("❌ --agent and --tool are required for provider=agent_tool")
                return
            provider = {
                "type": "agent_tool",
                "project_id": pid,
                "agent_id": args.agent,
                "tool_name": args.tool,
            }
        else:
            if not args.url:
                print("❌ --url is required for provider=http")
                return
            provider = {
                "type": "http",
                "project_id": pid,
                "url": args.url,
                "method": (args.method or "POST").upper(),
            }

        spec = {
            "name": args.name,
            "version": args.version,
            "description": args.description,
            "mode": args.mode,
            "owner_agent": args.owner_agent,
            "function_id": args.function_id,
            "provider": provider,
            "request_schema": req_schema,
            "response_schema": resp_schema,
            "limits": {
                "max_concurrency": args.max_concurrency,
                "rate_per_minute": args.rate_per_minute,
                "timeout_sec": args.timeout,
            },
            "status": "active",
        }
        res = requests.post(f"{base_url}/hermes/register", json={"project_id": pid, "spec": spec}, timeout=15)
        if res.status_code != 200:
            print(f"❌ Register failed: {res.text}")
            return
        print(f"✅ Protocol registered: {args.name}@{args.version} in {pid}")

    elif args.subcommand == "clause-template":
        req_schema = json.loads(args.request_schema) if args.request_schema else {"type": "object"}
        resp_schema = json.loads(args.response_schema) if args.response_schema else {"type": "object"}
        owner = (args.owner_agent or "").strip()
        provider_type = args.provider
        provider: dict
        if provider_type == "http":
            provider = {
                "type": "http",
                "url": (args.url or "http://127.0.0.1:18080/endpoint").strip(),
                "method": (args.method or "POST").upper(),
            }
        else:
            provider = {
                "type": "agent_tool",
                "agent_id": (args.agent or owner or "owner_agent").strip(),
                "tool_name": (args.tool or "run_command").strip(),
            }

        clause = {
            "id": args.id,
            "owner_agent": owner,
            "summary": args.summary or f"Executable clause for {args.id}",
            "provider": provider,
            "io": {
                "request_schema": req_schema,
                "response_schema": resp_schema,
            },
            "runtime": {
                "mode": args.mode,
                "timeout_sec": int(args.timeout),
                "rate_per_minute": int(args.rate),
                "max_concurrency": int(args.concurrency),
            },
        }
        print(json.dumps(clause, ensure_ascii=False, indent=2))

    elif args.subcommand == "call":
        payload = json.loads(args.payload) if args.payload else {}
        req = {
            "project_id": pid,
            "caller_id": args.caller,
            "name": args.name,
            "version": args.version,
            "mode": args.mode,
            "payload": payload,
        }
        res = requests.post(f"{base_url}/hermes/invoke", json=req, timeout=20)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "route":
        payload = json.loads(args.payload) if args.payload else {}
        req = {
            "project_id": pid,
            "caller_id": args.caller,
            "target_agent": args.target,
            "function_id": args.function,
            "mode": args.mode,
            "payload": payload,
        }
        res = requests.post(f"{base_url}/hermes/route", json=req, timeout=20)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "job":
        res = requests.get(f"{base_url}/hermes/jobs/{args.job_id}", params={"project_id": pid}, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "history":
        params = {"project_id": pid, "limit": args.limit}
        if args.name:
            params["name"] = args.name
        res = requests.get(f"{base_url}/hermes/invocations", params=params, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "contract-register":
        with open(args.file, "r", encoding="utf-8") as f:
            contract = json.load(f)
        res = requests.post(
            f"{base_url}/hermes/contracts/register",
            json={"project_id": pid, "contract": contract},
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "contract-commit":
        res = requests.post(
            f"{base_url}/hermes/contracts/commit",
            json={"project_id": pid, "title": args.title, "version": args.version, "agent_id": args.agent},
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "contract-resolve":
        res = requests.get(
            f"{base_url}/hermes/contracts/resolved",
            params={"project_id": pid, "title": args.title, "version": args.version},
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "contract-list":
        res = requests.get(
            f"{base_url}/hermes/contracts/list",
            params={"project_id": pid, "include_disabled": bool(getattr(args, "include_disabled", False))},
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "contract-disable":
        res = requests.post(
            f"{base_url}/hermes/contracts/disable",
            json={
                "project_id": pid,
                "title": args.title,
                "version": args.version,
                "agent_id": args.agent,
                "reason": args.reason,
            },
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "port-reserve":
        res = requests.post(
            f"{base_url}/hermes/ports/reserve",
            json={
                "project_id": pid,
                "owner_id": args.owner,
                "preferred_port": (None if int(args.preferred or 0) <= 0 else int(args.preferred)),
                "min_port": int(args.min_port),
                "max_port": int(args.max_port),
                "note": args.note,
            },
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "port-release":
        res = requests.post(
            f"{base_url}/hermes/ports/release",
            json={
                "project_id": pid,
                "owner_id": args.owner,
                "port": (None if int(args.port or 0) <= 0 else int(args.port)),
            },
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "port-list":
        res = requests.get(f"{base_url}/hermes/ports/list", params={"project_id": pid}, timeout=20)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
