#!/usr/bin/env python3
"""Animal World (Hermes-dominated): all module interactions go through Hermes route API."""
from __future__ import annotations

import json
import random
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gods.config import runtime_config, ProjectConfig
from gods.hermes import hermes_service


@dataclass
class LocalService:
    name: str
    server: ThreadingHTTPServer
    thread: threading.Thread
    port: int


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200):
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _make_handler(fn: Callable[[dict[str, Any]], dict[str, Any]]):
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(n) if n > 0 else b"{}"
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {}
            result = fn(payload)
            _json_response(self, result)

        def log_message(self, fmt, *args):
            return

    return _Handler


def _start_service(name: str, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> LocalService:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(fn))
    t = threading.Thread(target=srv.serve_forever, daemon=True, name=f"hermes_{name}_srv")
    t.start()
    return LocalService(name=name, server=srv, thread=t, port=int(srv.server_port))


def _apply_patch(state: dict[str, Any], patch: dict[str, Any]):
    for k, v in patch.items():
        state[k] = float(v)


def run_demo(project_id: str = "animal_world_hermes", steps: int = 40, seed: int = 42) -> dict[str, Any]:
    random.seed(seed)
    runtime_config.projects[project_id] = ProjectConfig(
        name="Animal World Hermes",
        hermes_allow_agent_tool_provider=False,
    )
    runtime_config.current_project = project_id
    runtime_config.save()

    def ground_balance(payload: dict[str, Any]) -> dict[str, Any]:
        s = dict(payload.get("state") or {})
        soil = float(s.get("soil", 80.0))
        grass = float(s.get("grass", 120.0))
        sheep = float(s.get("sheep", 20.0))
        tiger = float(s.get("tiger", 4.0))
        regen = grass * 0.008
        consume = sheep * 0.012 + tiger * 0.015
        return {"state_patch": {"soil": max(10.0, min(160.0, soil + regen - consume))}}

    def grass_grow(payload: dict[str, Any]) -> dict[str, Any]:
        s = dict(payload.get("state") or {})
        soil = float(s.get("soil", 80.0))
        grass = float(s.get("grass", 120.0))
        growth = max(0.2, 1.8 + soil * 0.03 - grass * 0.01)
        return {"state_patch": {"grass": max(0.0, grass + growth)}}

    def sheep_graze(payload: dict[str, Any]) -> dict[str, Any]:
        s = dict(payload.get("state") or {})
        sheep = float(s.get("sheep", 20.0))
        grass = float(s.get("grass", 120.0))
        eaten = min(grass, sheep * 0.3)
        sheep_next = max(0.0, sheep + eaten * 0.06 - sheep * 0.03)
        return {"state_patch": {"sheep": sheep_next, "grass": max(0.0, grass - eaten)}}

    def tiger_hunt(payload: dict[str, Any]) -> dict[str, Any]:
        s = dict(payload.get("state") or {})
        tiger = float(s.get("tiger", 4.0))
        sheep = float(s.get("sheep", 20.0))
        hunted = min(sheep * 0.2, tiger * 0.22)
        tiger_next = max(0.0, tiger + hunted * 0.04 - tiger * 0.05)
        return {"state_patch": {"tiger": tiger_next, "sheep": max(0.0, sheep - hunted)}}

    services = [
        _start_service("ground", ground_balance),
        _start_service("grass", grass_grow),
        _start_service("sheep", sheep_graze),
        _start_service("tiger", tiger_hunt),
    ]

    try:
        ports = {s.name: s.port for s in services}

        from gods.hermes.models import ProtocolSpec

        def reg(name: str, owner: str, fnid: str, path_name: str):
            url = f"http://127.0.0.1:{ports[path_name]}/fn/{fnid}"
            spec = ProtocolSpec(
                name=name,
                version="1.0.0",
                description=f"{owner}.{fnid}",
                mode="both",
                owner_agent=owner,
                function_id=fnid,
                provider={
                    "type": "http",
                    "project_id": project_id,
                    "url": url,
                    "method": "POST",
                },
                request_schema={
                    "type": "object",
                    "required": ["state", "step"],
                    "properties": {
                        "step": {"type": "integer"},
                        "state": {"type": "object"},
                    },
                },
                response_schema={
                    "type": "object",
                    "required": ["status_code", "result"],
                    "properties": {
                        "status_code": {"type": "integer"},
                        "result": {
                            "type": "object",
                            "required": ["state_patch"],
                            "properties": {
                                "state_patch": {"type": "object"},
                            },
                        },
                    },
                },
            )
            hermes_service.register(project_id, spec)

        reg("ground.balance", "ground", "balance", "ground")
        reg("grass.grow", "grass", "grow", "grass")
        reg("sheep.graze", "sheep", "graze", "sheep")
        reg("tiger.hunt", "tiger", "hunt", "tiger")

        contract = {
            "title": "ecosystem.core",
            "version": "1.0.0",
            "description": "Core ecosystem contract for ground/grass/sheep/tiger routing.",
            "submitter": "ground",
            "committers": ["ground", "grass", "sheep", "tiger"],
            "status": "active",
            "default_obligations": [],
            "obligations": {
                "ground": [
                    {
                        "id": "balance",
                        "provider": {
                            "type": "http",
                            "url": f"http://127.0.0.1:{ports['ground']}/fn/balance",
                            "method": "POST",
                        },
                        "io": {
                            "request_schema": {"type": "object"},
                            "response_schema": {"type": "object"},
                        },
                        "runtime": {"mode": "sync", "timeout_sec": 10},
                    }
                ],
                "grass": [
                    {
                        "id": "grow",
                        "provider": {
                            "type": "http",
                            "url": f"http://127.0.0.1:{ports['grass']}/fn/grow",
                            "method": "POST",
                        },
                        "io": {
                            "request_schema": {"type": "object"},
                            "response_schema": {"type": "object"},
                        },
                        "runtime": {"mode": "sync", "timeout_sec": 10},
                    }
                ],
                "sheep": [
                    {
                        "id": "graze",
                        "provider": {
                            "type": "http",
                            "url": f"http://127.0.0.1:{ports['sheep']}/fn/graze",
                            "method": "POST",
                        },
                        "io": {
                            "request_schema": {"type": "object"},
                            "response_schema": {"type": "object"},
                        },
                        "runtime": {"mode": "sync", "timeout_sec": 10},
                    }
                ],
                "tiger": [
                    {
                        "id": "hunt",
                        "provider": {
                            "type": "http",
                            "url": f"http://127.0.0.1:{ports['tiger']}/fn/hunt",
                            "method": "POST",
                        },
                        "io": {
                            "request_schema": {"type": "object"},
                            "response_schema": {"type": "object"},
                        },
                        "runtime": {"mode": "sync", "timeout_sec": 10},
                    }
                ],
            },
        }
        hermes_service.contracts.register(project_id, contract)
        for a in ["grass", "sheep", "tiger"]:
            hermes_service.contracts.commit(project_id, "ecosystem.core", "1.0.0", a)

        state = {"sheep": 22.0, "tiger": 4.0, "grass": 130.0, "soil": 85.0}
        history = []

        for step in range(1, steps + 1):
            for target, fnid in [
                ("ground", "balance"),
                ("grass", "grow"),
                ("sheep", "graze"),
                ("tiger", "hunt"),
            ]:
                res = hermes_service.route(
                    project_id=project_id,
                    caller_id="orchestrator",
                    target_agent=target,
                    function_id=fnid,
                    payload={"state": state, "step": step},
                    mode="sync",
                )
                if not res.ok:
                    raise RuntimeError(f"route failed {target}.{fnid}: {res.error}")
                body = (((res.result or {}).get("result") or {}))
                patch = body.get("state_patch") if isinstance(body, dict) else None
                if isinstance(patch, dict):
                    _apply_patch(state, patch)

            # keep sane bounds
            for key in ("sheep", "tiger", "grass", "soil"):
                state[key] = round(max(0.0, float(state[key])), 4)
            history.append({"step": step, **state})

        listed = hermes_service.contracts.list(project_id, include_disabled=True)
        contract_snapshot = next(
            (x for x in listed if x.get("title") == "ecosystem.core" and x.get("version") == "1.0.0"),
            {},
        )
        invocations = hermes_service.list_invocations(project_id, limit=10000)

        out_dir = Path("reports") / "animal_world_hermes_run"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "summary.json"
        summary = {
            "project_id": project_id,
            "steps": steps,
            "final_state": state,
            "history_tail": history[-10:],
            "route_invocation_count": len(invocations),
            "contract_snapshot": contract_snapshot,
            "ports": ports,
        }
        out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    finally:
        for svc in services:
            svc.server.shutdown()
            svc.server.server_close()


if __name__ == "__main__":
    out = run_demo()
    print(json.dumps({
        "project_id": out["project_id"],
        "final_state": out["final_state"],
        "route_invocation_count": out["route_invocation_count"],
    }, ensure_ascii=False, indent=2))
