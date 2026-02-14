"""
一键初始化图书馆单 Agent 项目并启动。

功能：
1. 可选重置项目目录和配置
2. 创建/切换项目
3. 创建 librarian Agent
4. 仅保留 librarian 为 active
5. 启动项目
6. 可选等待后输出状态摘要
"""
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

import requests


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PROJECT_ID = "library_single_agent"
DEFAULT_AGENT_ID = "librarian"


LIBRARIAN_DIRECTIVES = """# Agent: librarian

## 总任务
独立构建一个完整的图书馆管理系统（Library Management System），并在你的领地内实现、测试、修复并验证可运行。

## 单 Agent 约束
- 当前为单 Agent 开发测试，禁止社交协商与消息交互。
- 仅在 `projects/library_single_agent/agents/librarian/` 内操作。
- 优先推进实现与验证，避免重复探索动作。

## 功能要求
1. 图书管理：增删改查
2. 用户管理：注册、查询
3. 借阅归还：可借状态、借阅记录、归还逻辑
4. 查询统计：库存、借阅概览
5. 可运行入口：CLI 或 HTTP
6. 自动化测试

## 完成标准（DoD）
- 项目结构清晰，包含 README
- 核心功能可运行
- 测试命令可执行并通过
- 将最终运行与测试结果记录到 memory
"""


def _must_ok(resp: requests.Response, step: str):
    if resp.status_code >= 400:
        raise RuntimeError(f"{step} failed: HTTP {resp.status_code} {resp.text}")


def _wait_health(base_url: str, timeout_sec: int = 20):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Server not healthy at {base_url} within {timeout_sec}s")


def _delete_project_if_exists(base_url: str, project_id: str):
    # 无论是否存在都尝试删除，404 视为可接受
    r = requests.delete(f"{base_url}/projects/{project_id}", timeout=10)
    if r.status_code not in (200, 404):
        raise RuntimeError(f"delete project failed: HTTP {r.status_code} {r.text}")


def _switch_project(base_url: str, project_id: str):
    cfg = requests.get(f"{base_url}/config", timeout=10).json()
    cfg["current_project"] = project_id
    r = requests.post(f"{base_url}/config/save", json=cfg, timeout=10)
    _must_ok(r, "switch current_project")


def _deactivate_non_target_agents(base_url: str, project_id: str, target_agent: str):
    cfg = requests.get(f"{base_url}/config", timeout=10).json()
    proj = cfg["projects"].get(project_id, {})
    active = list(proj.get("active_agents", []))
    proj["active_agents"] = [a for a in active if a == target_agent]
    if target_agent not in proj["active_agents"]:
        proj["active_agents"].append(target_agent)
    cfg["projects"][project_id] = proj
    r = requests.post(f"{base_url}/config/save", json=cfg, timeout=10)
    _must_ok(r, "update active_agents")


def _ensure_agent(base_url: str, agent_id: str, directives: str):
    # 先尝试删除，避免重跑时报 Agent exists
    requests.delete(f"{base_url}/agents/{agent_id}", timeout=10)
    r = requests.post(
        f"{base_url}/agents/create",
        json={"agent_id": agent_id, "directives": directives},
        timeout=20,
    )
    _must_ok(r, "create agent")


def _show_status(base_url: str, project_id: str):
    cfg = requests.get(f"{base_url}/config", timeout=10).json()
    proj = cfg["projects"].get(project_id, {})
    print("\n=== STATUS ===")
    print(f"current_project: {cfg.get('current_project')}")
    print(f"project: {project_id}")
    print(f"simulation_enabled: {proj.get('simulation_enabled')}")
    print(f"active_agents: {proj.get('active_agents', [])}")

    r = requests.get(f"{base_url}/agents/status", params={"project_id": project_id}, timeout=10)
    if r.status_code == 200:
        data = r.json()
        for item in data.get("agents", []):
            print(
                f"- {item.get('agent_id')}: status={item.get('status')}, "
                f"last_pulse={item.get('last_pulse_at')}, next={item.get('next_eligible_at')}"
            )


def main():
    parser = argparse.ArgumentParser(description="Bootstrap and start library single-agent project.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID)
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the project before start.")
    parser.add_argument("--wait-sec", type=int, default=8, help="Wait seconds after start before showing status.")
    args = parser.parse_args()

    _wait_health(args.base_url, timeout_sec=20)

    # 先停当前项目（若存在）
    requests.post(f"{args.base_url}/projects/{args.project_id}/stop", timeout=10)

    if args.reset:
        _delete_project_if_exists(args.base_url, args.project_id)
        proj_dir = Path("projects") / args.project_id
        if proj_dir.exists():
            shutil.rmtree(proj_dir)

    # 创建项目（已存在会返回 error，属于可接受分支）
    r = requests.post(f"{args.base_url}/projects/create", json={"id": args.project_id}, timeout=10)
    if not (r.status_code == 200 and r.json().get("status") == "success"):
        payload = r.json()
        if payload.get("error") != "Project exists":
            _must_ok(r, "create project")

    _switch_project(args.base_url, args.project_id)
    _ensure_agent(args.base_url, args.agent_id, LIBRARIAN_DIRECTIVES)
    _deactivate_non_target_agents(args.base_url, args.project_id, args.agent_id)

    r = requests.post(f"{args.base_url}/projects/{args.project_id}/start", timeout=10)
    _must_ok(r, "start project")

    if args.wait_sec > 0:
        time.sleep(args.wait_sec)
    _show_status(args.base_url, args.project_id)
    print("\nBootstrap done.")


if __name__ == "__main__":
    main()
