"""CLI context observability commands (Janus)."""
from __future__ import annotations

import json

import requests

from cli.utils import get_base_url


def cmd_context(args):
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        pid = args.project or cfg.get("current_project", "default")
    except Exception:
        pid = args.project or "default"

    if args.subcommand == "preview":
        try:
            res = requests.get(
                f"{base}/projects/{pid}/context/preview",
                params={"agent_id": args.agent},
                timeout=10,
            )
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ context preview failed: {e}")

    elif args.subcommand == "reports":
        try:
            res = requests.get(
                f"{base}/projects/{pid}/context/reports",
                params={"agent_id": args.agent, "limit": args.limit},
                timeout=10,
            )
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ context reports failed: {e}")

    elif args.subcommand == "pulse":
        try:
            if args.action == "list":
                res = requests.get(
                    f"{base}/projects/{pid}/context/pulses",
                    params={
                        "agent_id": args.agent,
                        "from_seq": int(args.from_seq or 0),
                        "limit": int(args.limit or 200),
                    },
                    timeout=10,
                )
                body = res.json()
                pulses = list(body.get("pulses", []) or [])
                print(json.dumps({"count": len(pulses), "errors": body.get("errors", []), "pulses": pulses}, ensure_ascii=False, indent=2))
            elif args.action == "inspect":
                res = requests.get(
                    f"{base}/projects/{pid}/context/pulses",
                    params={
                        "agent_id": args.agent,
                        "from_seq": int(args.from_seq or 0),
                        "limit": int(args.limit or 1000),
                    },
                    timeout=10,
                )
                body = res.json()
                pulse_id = str(args.pulse_id or "")
                pulse = None
                for p in list(body.get("pulses", []) or []):
                    if str(p.get("pulse_id", "")) == pulse_id:
                        pulse = p
                        break
                print(json.dumps({"pulse": pulse, "errors": body.get("errors", [])}, ensure_ascii=False, indent=2))
            elif args.action == "validate":
                res = requests.get(
                    f"{base}/projects/{pid}/context/pulses",
                    params={
                        "agent_id": args.agent,
                        "from_seq": int(args.from_seq or 0),
                        "limit": int(args.limit or 1000),
                    },
                    timeout=10,
                )
                body = res.json()
                errors = list(body.get("errors", []) or [])
                print(json.dumps({"ok": not errors, "error_count": len(errors), "errors": errors}, ensure_ascii=False, indent=2))
            else:
                print("❌ context pulse requires action: list|inspect|validate")
        except Exception as e:
            print(f"❌ context pulse failed: {e}")
