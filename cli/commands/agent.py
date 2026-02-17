"""CLI agent command handlers."""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import requests

from cli.utils import get_base_url


def _pid(args) -> str:
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        return args.project or cfg.get("current_project", "default")
    except Exception:
        return args.project or "default"


def _list_local_agents(project_id: str) -> list[str]:
    profile_dir = Path(f"projects/{project_id}/mnemosyne/agent_profiles")
    if not profile_dir.exists():
        return []
    return sorted(p.stem for p in profile_dir.glob("*.md") if p.is_file())


def cmd_agent(args):
    """Agent operations."""
    pid = _pid(args)
    base = get_base_url()

    if args.subcommand == "list":
        items = _list_local_agents(pid)
        print(json.dumps({"project_id": pid, "agents": items}, ensure_ascii=False, indent=2))
        return

    if args.subcommand == "activate":
        aid = str(args.id or "").strip()
        if not aid:
            print("❌ agent id is required")
            return
        try:
            cfg = requests.get(f"{base}/config", timeout=5).json()
            proj = cfg.get("projects", {}).get(pid, {})
            active = list(proj.get("active_agents", []))
            if aid not in active:
                active.append(aid)
                cfg["projects"][pid]["active_agents"] = active
                requests.post(f"{base}/config/save", json=cfg, timeout=5)
            print(json.dumps({"project_id": pid, "agent_id": aid, "active": True}, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ activate failed: {e}")
        return

    if args.subcommand == "deactivate":
        aid = str(args.id or "").strip()
        if not aid:
            print("❌ agent id is required")
            return
        try:
            cfg = requests.get(f"{base}/config", timeout=5).json()
            proj = cfg.get("projects", {}).get(pid, {})
            active = list(proj.get("active_agents", []))
            if aid in active:
                active.remove(aid)
                cfg["projects"][pid]["active_agents"] = active
                requests.post(f"{base}/config/save", json=cfg, timeout=5)
            print(json.dumps({"project_id": pid, "agent_id": aid, "active": False}, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ deactivate failed: {e}")
        return

    if args.subcommand == "create":
        try:
            req = {"agent_id": args.id, "directives": args.directives}
            res = requests.post(f"{base}/agents/create", json=req, timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ create failed: {e}")
        return

    if args.subcommand == "delete":
        try:
            res = requests.delete(f"{base}/agents/{args.id}", timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ delete failed: {e}")
        return

    if args.subcommand == "status":
        try:
            res = requests.get(f"{base}/agents/status", params={"project_id": pid}, timeout=5)
            data = res.json()
        except Exception as e:
            print(f"❌ 获取 agent 状态失败: {e}")
            return

        rows = data.get("agents", [])
        target = (args.agent_id or "").strip()
        if target:
            rows = [x for x in rows if x.get("agent_id") == target]

        if args.json:
            print(json.dumps({"project_id": pid, "agents": rows}, ensure_ascii=False, indent=2))
            return

        print(f"\n🧭 AGENT STATUS - Project: {pid}")
        if not rows:
            print("No agents found.")
            return
        for item in rows:
            lp = float(item.get("last_pulse_at", 0) or 0)
            ne = float(item.get("next_eligible_at", 0) or 0)
            lp_s = datetime.datetime.fromtimestamp(lp).strftime("%Y-%m-%d %H:%M:%S") if lp > 0 else "N/A"
            ne_s = datetime.datetime.fromtimestamp(ne).strftime("%Y-%m-%d %H:%M:%S") if ne > 0 else "N/A"
            print(f"- {item.get('agent_id', '')}: {item.get('status', 'unknown')}")
            print(f"  Last Pulse: {lp_s}")
            print(f"  Next Eligible: {ne_s}")
            print(f"  Pending Inbox: {bool(item.get('has_pending_inbox', False))}")
            err = str(item.get("last_error", "") or "").strip()
            if err:
                print(f"  Last Error: {err}")
        return

    if args.subcommand == "strategy":
        try:
            cfg = requests.get(f"{base}/config", timeout=5).json()
            proj = cfg.get("projects", {}).get(pid, {})
            settings = proj.get("agent_settings", {}) or {}
            allowed = {"react_graph", "freeform"}
            if args.action == "list":
                rows = []
                for aid, row in settings.items():
                    rows.append(
                        {
                            "agent_id": aid,
                            "phase_strategy": row.get("phase_strategy", proj.get("phase_strategy", "react_graph")),
                        }
                    )
                print(json.dumps({"project_id": pid, "items": rows}, ensure_ascii=False, indent=2))
                return
            aid = str(args.agent or "").strip()
            if not aid:
                print("❌ --agent is required")
                return
            if args.action == "get":
                row = settings.get(aid, {}) or {}
                print(
                    json.dumps(
                        {
                            "project_id": pid,
                            "agent_id": aid,
                            "phase_strategy": row.get("phase_strategy", proj.get("phase_strategy", "react_graph")),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return
            if args.action == "set":
                strategy = str(args.strategy or "").strip()
                if strategy not in allowed:
                    print("❌ --strategy must be one of: react_graph, freeform")
                    return
                cfg.setdefault("projects", {}).setdefault(pid, {}).setdefault("agent_settings", {})
                cfg["projects"][pid]["agent_settings"].setdefault(aid, {})
                cfg["projects"][pid]["agent_settings"][aid]["phase_strategy"] = strategy
                res = requests.post(f"{base}/config/save", json=cfg, timeout=5)
                print(json.dumps(res.json(), ensure_ascii=False, indent=2))
                return
            print("❌ unknown strategy action")
        except Exception as e:
            print(f"❌ strategy operation failed: {e}")
        return

    agent_file = Path(f"projects/{pid}/mnemosyne/agent_profiles/{args.id}.md")

    if not agent_file.exists():
        print(f"❌ Being '{args.id}' not found in world '{pid}'.")
        return

    if args.subcommand == "view":
        print(f"--- DIRECTIVES FOR {args.id} IN {pid} ---")
        print(agent_file.read_text(encoding="utf-8"))
    elif args.subcommand == "edit":
        print(f"📝 Enter new directives for {args.id} (End with Ctrl-D/Ctrl-Z):")
        new_directives = sys.stdin.read()
        if new_directives.strip():
            agent_file.write_text(new_directives, encoding="utf-8")
            print(f"✅ Directives for {args.id} updated.")
        else:
            print("🚫 Canceled.")
