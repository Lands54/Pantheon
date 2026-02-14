#!/usr/bin/env python3
"""
Autonomous emergent run for Animal World project.
Only seeds identity + shared mission, then lets agents self-organize.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage

from gods.config import runtime_config, ProjectConfig, AgentModelConfig
from gods.protocols import build_knowledge_graph
from gods.agents.base import GodAgent

PROJECT_ID = "animal_world_emergent"
AGENTS = ["sheep", "tiger", "grass", "ground"]
MISSION = "构建一个可长期运行的生态系统模拟程序。你们自行分工、协商、写代码、集成和测试。"


def _agent_directive(agent_id: str, role: str) -> str:
    return f"""# Agent: {agent_id}

## 世界总职责
{MISSION}

## 你的本体职责
{role}

## 自治原则
- 你可以自发决定下一步任务，不等待人类逐条指令。
- 你只允许修改你自己领地 `projects/{PROJECT_ID}/agents/{agent_id}/` 下的代码与文件，不得越界。
- 你可以通过私聊与他者协作协商模块接口；接口可用 HTTP、本地文件、消息协议或你们自选方案。
- 达成双边/多边共识后，请调用 [[record_protocol(topic="...", relation="...", object="...", clause="...", counterparty="...")]] 记录协议。
- 当你需要他者实现某模块时，优先通过 [[send_message(to_id="...", message="...")]] 协商。
- 你可以用 run_command 在自己领地执行 Python 项目操作。
- 不允许连续两轮只做 check_inbox/list_dir；若收件箱为空，必须主动向至少一个代理发起协商消息。
- 在前两轮内至少创建一个你自己的实现文件（如 `logic.py`、`api.py`、`contract.json`、`README.md`）。
- 你的目标是可集成调用，不是孤立代码；请主动形成可被他者调用的接口约定。
"""


def setup_project(reset: bool = True):
    proj_root = Path("projects") / PROJECT_ID
    if reset and proj_root.exists():
        shutil.rmtree(proj_root)

    if PROJECT_ID not in runtime_config.projects:
        runtime_config.projects[PROJECT_ID] = ProjectConfig(name="Animal World Emergent")

    proj = runtime_config.projects[PROJECT_ID]
    proj.name = "Animal World Emergent"
    proj.active_agents = list(AGENTS)
    proj.autonomous_parallel = True
    proj.autonomous_batch_size = len(AGENTS)
    proj.command_timeout_sec = 90
    proj.command_max_parallel = 4
    for agent in AGENTS:
        if agent not in proj.agent_settings:
            proj.agent_settings[agent] = AgentModelConfig()
        proj.agent_settings[agent].model = "stepfun/step-3.5-flash:free"

    runtime_config.current_project = PROJECT_ID
    runtime_config.save()

    roles = {
        "sheep": "羊群代理：关注羊群行为、摄食、繁衍和种群稳定。",
        "tiger": "虎群代理：关注捕食压力、猎物关系和食物链上层稳定。",
        "grass": "草地代理：关注草生长、恢复力与资源供给。",
        "ground": "地面代理：关注土壤养分循环、全局集成、启动脚本和运行验证。",
    }

    for agent in AGENTS:
        agent_dir = proj_root / "agents" / agent
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "agent.md").write_text(_agent_directive(agent, roles[agent]), encoding="utf-8")
        (agent_dir / "memory.md").write_text("", encoding="utf-8")


def run_emergent_rounds(rounds: int = 6) -> list[dict]:
    """
    Fully parallel autonomous pulses:
    each round all agents pulse concurrently with the same global decree.
    """
    run_log = []
    for i in range(1, rounds + 1):
        context = (
            f"SACRED DECREE ROUND {i}: "
            "完全并行推进。每位代理仅实现自己模块，先协商接口再集成；若收件箱为空也要主动外联协商。"
            if i == 1
            else f"EXISTENCE_PULSE ROUND {i}: 并行继续推进；保持边界，不越界修改他人领地。"
        )
        round_events = []

        def pulse(agent_id: str):
            agent = GodAgent(agent_id=agent_id, project_id=PROJECT_ID)
            state = {
                "project_id": PROJECT_ID,
                "messages": [HumanMessage(content=context, name="High Overseer")],
                "current_speaker": "",
                "debate_round": i,
                "inbox": {},
                "context": context,
                "next_step": "",
            }
            out = agent.process(state)
            last = out.get("messages", [])[-1] if out.get("messages") else None
            return {
                "node": agent_id,
                "speaker": getattr(last, "name", agent_id) if last else agent_id,
                "content": str(getattr(last, "content", ""))[:600],
                "next_step": out.get("next_step", ""),
            }

        with ThreadPoolExecutor(max_workers=len(AGENTS)) as ex:
            futs = [ex.submit(pulse, agent_id) for agent_id in AGENTS]
            for fut in as_completed(futs):
                try:
                    round_events.append(fut.result())
                except Exception as e:
                    round_events.append({"node": "system", "speaker": "system", "content": f"pulse error: {e}", "next_step": "error"})

        run_log.append({"round": i, "events": round_events})
    return run_log


def collect_artifacts() -> dict:
    proj_root = Path("projects") / PROJECT_ID
    agents_root = proj_root / "agents"
    files_by_agent = {}
    for agent_dir in sorted(agents_root.iterdir()):
        if not agent_dir.is_dir():
            continue
        rel_files = []
        for p in sorted(agent_dir.rglob("*")):
            if p.is_file():
                rel = p.relative_to(agent_dir).as_posix()
                if rel in {"agent.md", "memory.md"}:
                    continue
                rel_files.append(rel)
        files_by_agent[agent_dir.name] = rel_files

    proto_file = proj_root / "protocols" / "events.jsonl"
    protocol_count = 0
    if proto_file.exists():
        with proto_file.open("r", encoding="utf-8") as f:
            protocol_count = sum(1 for line in f if line.strip())

    graph = build_knowledge_graph(PROJECT_ID)
    graph_path = proj_root / "knowledge" / "knowledge_graph.json"

    return {
        "files_by_agent": files_by_agent,
        "protocol_count": protocol_count,
        "graph_nodes": len(graph.get("nodes", [])),
        "graph_edges": len(graph.get("edges", [])),
        "graph_path": str(graph_path),
    }


def main():
    setup_project(reset=True)
    log = run_emergent_rounds(rounds=6)
    artifacts = collect_artifacts()

    report = {
        "project_id": PROJECT_ID,
        "timestamp": int(time.time()),
        "rounds": len(log),
        "artifacts": artifacts,
        "round_log": log,
    }
    report_path = Path("projects") / PROJECT_ID / "reports" / "emergent_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report_path": str(report_path), **artifacts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
