"""CLI commands for Mnemosyne archives."""
from __future__ import annotations

import json
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
