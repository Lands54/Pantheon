"""CLI commands for Mnemosyne archives."""
from __future__ import annotations

import json
import base64
from pathlib import Path
import requests

from cli.utils import get_base_url


def _current_project(base_url: str, project_arg: str | None) -> str:
    if project_arg:
        return project_arg
    cfg = requests.get(f"{base_url}/config", timeout=5).json()
    return cfg.get("current_project", "default")


def cmd_mnemosyne(args):
    base_url = get_base_url()
    pid = _current_project(base_url, getattr(args, "project", None))

    if args.subcommand == "write":
        payload = {
            "project_id": pid,
            "vault": args.vault,
            "author": args.author,
            "title": args.title,
            "content": args.content,
            "tags": [x.strip() for x in (args.tags or "").split(",") if x.strip()],
        }
        res = requests.post(f"{base_url}/mnemosyne/write", json=payload, timeout=20)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "list":
        res = requests.get(
            f"{base_url}/mnemosyne/list",
            params={"project_id": pid, "vault": args.vault, "limit": args.limit},
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "read":
        res = requests.get(
            f"{base_url}/mnemosyne/read/{args.entry_id}",
            params={"project_id": pid, "vault": args.vault},
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "artifact-list":
        res = requests.get(
            f"{base_url}/mnemosyne/artifacts",
            params={
                "project_id": pid,
                "scope": args.scope,
                "actor_id": args.actor,
                "owner_agent_id": args.owner,
                "limit": int(args.limit),
            },
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "artifact-head":
        res = requests.get(
            f"{base_url}/mnemosyne/artifacts/{args.artifact_id}",
            params={
                "project_id": pid,
                "actor_id": args.actor,
            },
            timeout=20,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "artifact-put-text":
        payload = {
            "project_id": pid,
            "scope": args.scope,
            "owner_agent_id": args.owner,
            "actor_id": args.actor,
            "content": args.content,
            "mime": args.mime,
            "tags": [x.strip() for x in str(args.tags or "").split(",") if x.strip()],
        }
        res = requests.post(f"{base_url}/mnemosyne/artifacts/text", json=payload, timeout=30)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "artifact-put-file":
        fp = Path(str(args.file or "").strip())
        if not fp.exists() or not fp.is_file():
            print(json.dumps({"error": f"file not found: {fp}"}, ensure_ascii=False, indent=2))
            return
        raw = fp.read_bytes()
        payload = {
            "project_id": pid,
            "scope": args.scope,
            "owner_agent_id": args.owner,
            "actor_id": args.actor,
            "mime": args.mime or "application/octet-stream",
            "tags": [x.strip() for x in str(args.tags or "").split(",") if x.strip()],
            "content_base64": base64.b64encode(raw).decode("utf-8"),
        }
        res = requests.post(f"{base_url}/mnemosyne/artifacts/bytes", json=payload, timeout=60)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
