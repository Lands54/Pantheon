#!/usr/bin/env python3
"""
End-to-end Animal World simulation setup and test.
Creates a distributed multi-agent project, writes role-owned logic,
runs simulation, records protocols, and builds a knowledge graph.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gods.config import runtime_config, ProjectConfig, AgentModelConfig
from gods.protocols import build_knowledge_graph
from gods.tools.communication import record_protocol
from gods.tools.filesystem import write_file
from gods.tools.execution import run_command

PROJECT_ID = "animal_world"
AGENTS = ["sheep", "tiger", "grass", "ground"]
GLOBAL_MISSION = "构建一个可以长期运行的生态系统"

AGENT_DIRECTIVES = {
    "sheep": "构建并维护羊群行为逻辑，确保摄食、繁衍与生态平衡。",
    "tiger": "构建并维护虎群捕食逻辑，避免猎物灭绝并稳定食物链。",
    "grass": "构建并维护草地生长逻辑，为食草动物提供持续供给。",
    "ground": "构建并维护土壤与养分循环逻辑，调节系统恢复力并负责总调度。",
}

LOGIC_FILES = {
    "sheep": """def update(state):
    sheep = float(state.get("sheep", 20.0))
    grass = float(state.get("grass", 120.0))
    eaten = min(grass, sheep * 0.25)
    sheep_next = max(0.0, sheep + eaten * 0.07 - sheep * 0.03)
    state["sheep"] = sheep_next
    state["grass"] = max(0.0, grass - eaten)
    state["stats"]["sheep_food_intake"] += eaten
""",
    "tiger": """def update(state):
    tiger = float(state.get("tiger", 5.0))
    sheep = float(state.get("sheep", 20.0))
    hunted = min(sheep * 0.25, tiger * 0.18)
    tiger_next = max(0.0, tiger + hunted * 0.05 - tiger * 0.06)
    state["tiger"] = tiger_next
    state["sheep"] = max(0.0, sheep - hunted)
    state["stats"]["tiger_hunt"] += hunted
""",
    "grass": """def update(state):
    grass = float(state.get("grass", 120.0))
    soil = float(state.get("soil", 80.0))
    growth = max(0.8, 2.2 + soil * 0.04 - grass * 0.01)
    state["grass"] = max(0.0, grass + growth)
    state["stats"]["grass_growth"] += growth
""",
    "ground": """def update(state):
    soil = float(state.get("soil", 80.0))
    grass = float(state.get("grass", 120.0))
    sheep = float(state.get("sheep", 20.0))
    tiger = float(state.get("tiger", 5.0))
    pressure = sheep * 0.015 + tiger * 0.01
    regen = grass * 0.012
    soil_next = max(10.0, min(140.0, soil + regen - pressure))
    state["soil"] = soil_next
    state["stats"]["soil_regen"] += (soil_next - soil)
""",
}

SIM_RUNNER = """import json
import importlib.util
from pathlib import Path


def load_update(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.update


def main():
    base = Path(__file__).resolve().parents[1]
    sheep_update = load_update(base / "sheep" / "logic.py")
    tiger_update = load_update(base / "tiger" / "logic.py")
    grass_update = load_update(base / "grass" / "logic.py")
    ground_update = load_update(base / "ground" / "logic.py")

    state = {
        "sheep": 24.0,
        "tiger": 5.0,
        "grass": 135.0,
        "soil": 82.0,
        "stats": {
            "sheep_food_intake": 0.0,
            "tiger_hunt": 0.0,
            "grass_growth": 0.0,
            "soil_regen": 0.0,
        },
    }
    history = []
    for step in range(1, 81):
        grass_update(state)
        sheep_update(state)
        tiger_update(state)
        ground_update(state)

        # floor values
        for key in ("sheep", "tiger", "grass", "soil"):
            state[key] = round(max(0.0, state[key]), 4)

        snapshot = {
            "step": step,
            "sheep": state["sheep"],
            "tiger": state["tiger"],
            "grass": state["grass"],
            "soil": state["soil"],
        }
        history.append(snapshot)

    report = {
        "steps": len(history),
        "final_state": history[-1],
        "history_tail": history[-10:],
        "stats": state["stats"],
    }
    out = Path(__file__).resolve().parent / "animal_world_output.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["final_state"], ensure_ascii=False))


if __name__ == "__main__":
    main()
"""


def ensure_project_and_agents():
    if PROJECT_ID not in runtime_config.projects:
        runtime_config.projects[PROJECT_ID] = ProjectConfig(name="Animal World")
    proj = runtime_config.projects[PROJECT_ID]
    proj.name = "Animal World"
    proj.active_agents = list(AGENTS)
    for agent in AGENTS:
        if agent not in proj.agent_settings:
            proj.agent_settings[agent] = AgentModelConfig()
    runtime_config.current_project = PROJECT_ID
    runtime_config.save()

    for agent in AGENTS:
        agent_dir = Path("projects") / PROJECT_ID / "agents" / agent
        agent_dir.mkdir(parents=True, exist_ok=True)
        directive = (
            f"# Agent: {agent}\n\n"
            f"## 总职责\n{GLOBAL_MISSION}\n\n"
            f"## 自身职责\n{AGENT_DIRECTIVES[agent]}\n"
        )
        (agent_dir / "agent.md").write_text(directive, encoding="utf-8")


def write_distributed_logic():
    for agent, code in LOGIC_FILES.items():
        res = write_file.invoke(
            {
                "path": "logic.py",
                "content": code,
                "caller_id": agent,
                "project_id": PROJECT_ID,
            }
        )
        if "inscribed" not in res:
            raise RuntimeError(f"写入 {agent} 逻辑失败: {res}")

    # Ground owns simulation runner and is responsible for integration.
    res = write_file.invoke(
        {
            "path": "ecosystem_sim.py",
            "content": SIM_RUNNER,
            "caller_id": "ground",
            "project_id": PROJECT_ID,
        }
    )
    if "inscribed" not in res:
        raise RuntimeError(f"写入模拟器失败: {res}")


def record_protocols():
    entries = [
        ("sheep", "生态平衡协议", "consumes", "grass", "羊仅在草量充足时扩张，以避免草场崩溃", "grass"),
        ("tiger", "生态平衡协议", "preys_on", "sheep", "虎捕食强度随羊群规模调整，避免过猎", "sheep"),
        ("grass", "生态平衡协议", "depends_on", "soil", "草生长速率受土壤养分约束", "ground"),
        ("ground", "生态平衡协议", "regulates", "ecosystem", "地面负责养分循环与全局稳定策略", "all"),
    ]
    for subject, topic, relation, obj, clause, counterparty in entries:
        res = record_protocol.invoke(
            {
                "topic": topic,
                "relation": relation,
                "object": obj,
                "clause": clause,
                "counterparty": counterparty,
                "status": "agreed",
                "caller_id": subject,
                "project_id": PROJECT_ID,
            }
        )
        if "Protocol recorded" not in res:
            raise RuntimeError(f"记录协议失败: {res}")


def run_simulation():
    result = run_command.invoke(
        {
            "command": "python ecosystem_sim.py",
            "caller_id": "ground",
            "project_id": PROJECT_ID,
        }
    )
    if "exit=0" not in result:
        raise RuntimeError(f"模拟执行失败: {result}")
    return result


def verify_outputs():
    report_path = Path("projects") / PROJECT_ID / "agents" / "ground" / "animal_world_output.json"
    if not report_path.exists():
        raise RuntimeError(f"未找到模拟输出: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    final_state = report.get("final_state", {})
    if not final_state:
        raise RuntimeError("模拟输出缺少 final_state")
    if final_state.get("sheep", 0) <= 0 or final_state.get("grass", 0) <= 0:
        raise RuntimeError(f"生态系统未稳定，最终状态异常: {final_state}")
    return final_state, report_path


def build_graph():
    graph = build_knowledge_graph(PROJECT_ID)
    graph_path = Path("projects") / PROJECT_ID / "knowledge" / "knowledge_graph.json"
    if not graph_path.exists():
        raise RuntimeError("知识图谱文件未生成")
    return graph, graph_path


def main():
    ensure_project_and_agents()
    write_distributed_logic()
    record_protocols()
    sim_result = run_simulation()
    final_state, report_path = verify_outputs()
    graph, graph_path = build_graph()

    summary = {
        "project_id": PROJECT_ID,
        "final_state": final_state,
        "simulation_report": str(report_path),
        "knowledge_graph": str(graph_path),
        "graph_nodes": len(graph.get("nodes", [])),
        "graph_edges": len(graph.get("edges", [])),
        "execution_summary": sim_result[:300],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
