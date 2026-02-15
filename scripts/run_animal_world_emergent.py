#!/usr/bin/env python3
"""
Initialize Animal World for fully autonomous platform scheduling.

This script only:
1) creates/resets project and agent directives
2) enables autonomous simulation
3) seeds one kickoff message per agent inbox

After this, platform scheduler (server.py) owns all further execution.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gods.config import runtime_config, ProjectConfig, AgentModelConfig

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
- 达成双边/多边共识后，请调用 [[register_contract(contract_json="...")]] 并让各方 [[commit_contract(...)]]。
- 当你需要他者实现某模块时，优先通过 [[send_message(to_id="...", message="...")]] 协商。
- 你可以用 run_command 在自己领地执行 Python 项目操作。
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
    proj.simulation_enabled = True
    proj.autonomous_batch_size = len(AGENTS)
    proj.simulation_interval_min = 3
    proj.simulation_interval_max = 8
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
        profile = proj_root / "mnemosyne" / "agent_profiles" / f"{agent}.md"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(_agent_directive(agent, roles[agent]), encoding="utf-8")


def seed_kickoff_messages():
    """
    Put one kickoff message into each agent inbox.
    Scheduler prioritizes inbox_event and will pick these up automatically.
    """
    buffer_dir = Path("projects") / PROJECT_ID / "buffers"
    buffer_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()

    seeds = {
        "sheep": "请定义羊群模块的最小接口（输入/输出）并告知 tiger 与 ground。",
        "tiger": "请定义捕食模块接口，并与 sheep 协商交互参数。",
        "grass": "请定义草地生长模块接口，并与 ground 协商土壤耦合。",
        "ground": "请定义集成入口（例如 main.py 或 server 接口），并协调其他三方对接。",
    }

    for agent_id, content in seeds.items():
        inbox = buffer_dir / f"{agent_id}.jsonl"
        msg = {
            "timestamp": now,
            "from": "High Overseer",
            "type": "seed",
            "content": f"{MISSION}。{content} 达成协议后请 register_contract + commit_contract。",
        }
        with inbox.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def main():
    setup_project(reset=True)
    seed_kickoff_messages()

    out = {
        "project_id": PROJECT_ID,
        "mode": "platform_autonomous",
        "simulation_enabled": True,
        "autonomous_batch_size": len(AGENTS),
        "next_step": "启动/保持 server.py 运行，平台将自动调度。",
        "check_commands": [
            f"./temple.sh project switch {PROJECT_ID}",
            "./temple.sh check sheep",
            "./temple.sh check tiger",
            "./temple.sh check grass",
            "./temple.sh check ground",
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
