#!/usr/bin/env bash
set -euo pipefail

# One-shot helper:
# 1) restart API server
# 2) re-init animal world project
# 3) create agents with Python/Hermes constraints
# 4) start project simulation
#
# Usage:
#   ./scripts/restart_and_init_animal_world.sh [project_id]
#
# Optional env:
#   BASE_URL=http://localhost:8000
#   GODS_SERVER_LOG=/tmp/gods_server.log
#   GODS_SERVER_PID=/tmp/gods_server.pid
#   GODS_DOCKER_IMAGE=gods-agent-base:py311

PROJECT_ID="${1:-animal_world_lab}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
SERVER_LOG="${GODS_SERVER_LOG:-/tmp/gods_server.log}"
SERVER_PID_FILE="${GODS_SERVER_PID:-/tmp/gods_server.pid}"
DOCKER_IMAGE="${GODS_DOCKER_IMAGE:-gods-agent-base:py311}"

echo "==> Restarting server..."

# Stop by pid file first
if [[ -f "${SERVER_PID_FILE}" ]]; then
  OLD_PID="$(cat "${SERVER_PID_FILE}" || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    kill "${OLD_PID}" || true
    sleep 1
  fi
  rm -f "${SERVER_PID_FILE}"
fi

# Stop any process currently listening on :8000
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti tcp:8000 || true)"
  if [[ -n "${PIDS}" ]]; then
    kill ${PIDS} || true
    sleep 1
  fi
fi

nohup conda run -n gods_env python server.py >"${SERVER_LOG}" 2>&1 &
NEW_PID=$!
echo "${NEW_PID}" > "${SERVER_PID_FILE}"

echo "   server pid: ${NEW_PID}"
echo "   log: ${SERVER_LOG}"

echo "==> Waiting for health check..."
for i in $(seq 1 80); do
  if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
    echo "   server is ready"
    break
  fi
  if [[ "${i}" -eq 80 ]]; then
    echo "ERROR: server did not become ready in time"
    tail -n 120 "${SERVER_LOG}" || true
    exit 1
  fi
  sleep 0.5
done

echo "==> Initializing project: ${PROJECT_ID}"
BASE_URL="${BASE_URL}" PROJECT_ID="${PROJECT_ID}" DOCKER_IMAGE="${DOCKER_IMAGE}" python - <<'PY'
import json
import os
from pathlib import Path
import requests

base = os.environ.get("BASE_URL", "http://localhost:8000")
project_id = os.environ.get("PROJECT_ID", "animal_world_lab")
docker_image = os.environ.get("DOCKER_IMAGE", "gods-agent-base:py311")

agents = {
    "ground": "# Ground\n你负责系统集成、状态汇总、启动验证与总线治理。",
    "grass": "# Grass\n你负责草地生长、资源恢复、生产者侧接口。",
    "sheep": "# Sheep\n你负责羊群摄食、繁殖与种群稳定策略。",
    "tiger": "# Tiger\n你负责捕食压力、顶层捕食者行为与平衡约束。",
}

guide = """

---
Hermes + Python 执行规范（必须遵守）
1) 所有实现必须通过 Python 代码落地（.py 文件 + 可执行命令验证）。
2) 跨代理调用统一使用 HermesClient（优先 route），禁止假设对方文件结构。
3) 协商后先走 contract-register -> commit-contract -> resolve-contract，再实现代码。
4) 每完成一个可验证里程碑，调用 send_to_human 汇报：已完成内容/风险/下一步。
5) 禁止只提交自然语言协议或伪代码，必须给出可运行实现。

Python 示例：
```python
from gods.hermes.client import HermesClient
cli = HermesClient(base_url="http://localhost:8000")
ret = cli.route(
    project_id="%s",
    caller_id="ground",
    target_agent="grass",
    function_id="grow",
    payload={"state": {"grass": 10}},
    mode="sync",
)
print(ret)
```

[协商硬性规则]
必须先与相关代理充分协商，形成完整提案（目标、条款、可执行clause、责任分配、验收标准）后，才允许注册契约；禁止未协商先注册。

[契约执行模板 - 必须遵守]
你提交的 contract 必须是“可执行 clause”，不是文字说明。每条 clause 必须包含：
- id
- provider (type/url/method 或 agent_tool)
- io.request_schema
- io.response_schema
- runtime.mode/timeout_sec

最小可执行 contract 示例（可直接改后提交）：
```json
{
  "title": "Animal World Core Contract",
  "version": "1.0.0",
  "description": "Ecosystem runnable obligations",
  "submitter": "ground",
  "committers": ["grass", "sheep", "tiger"],
  "status": "active",
  "default_obligations": [
    {
      "id": "health_check",
      "summary": "basic health check",
      "provider": {
        "type": "http",
        "url": "http://127.0.0.1:18080/health",
        "method": "GET"
      },
      "io": {
        "request_schema": {"type": "object"},
        "response_schema": {"type": "object"}
      },
      "runtime": {"mode": "sync", "timeout_sec": 10}
    }
  ],
  "obligations": {
    "grass": [
      {
        "id": "grow",
        "summary": "grass growth tick",
        "provider": {
          "type": "http",
          "url": "http://127.0.0.1:18081/grow",
          "method": "POST"
        },
        "io": {
          "request_schema": {"type": "object"},
          "response_schema": {"type": "object"}
        },
        "runtime": {"mode": "sync", "timeout_sec": 10}
      }
    ]
  }
}
```

[强制协作规则]
1) 注册契约后，除发布者外，所有参与方必须显式 commit_contract 才算生效。
2) 只有当“发布者 + 全部参与方”都完成 commit 后，才允许进入正式实现阶段。
3) 若有人未 commit，不得宣称契约已达成。
""" % project_id

def req(method: str, path: str, **kwargs):
    r = requests.request(method, f"{base}{path}", timeout=30, **kwargs)
    return r

# Best-effort delete old project
req("DELETE", f"/projects/{project_id}")

r = req("POST", "/projects/create", json={"id": project_id})
r.raise_for_status()

cfg = req("GET", "/config").json()
cfg["current_project"] = project_id
req("POST", "/config/save", json=cfg).raise_for_status()

for aid, directives in agents.items():
    resp = req("POST", "/agents/create", json={"agent_id": aid, "directives": directives + guide})
    if resp.status_code not in (200, 400):  # 400 if exists (unlikely after recreate)
        resp.raise_for_status()

cfg = req("GET", "/config").json()
proj = cfg["projects"][project_id]
proj["active_agents"] = list(agents.keys())
proj["simulation_enabled"] = False
proj["simulation_interval_min"] = 8
proj["simulation_interval_max"] = 12
proj["phase_strategy"] = "freeform"
# Force docker runtime backend for agent command execution.
proj["command_executor"] = "docker"
proj["docker_enabled"] = True
proj["docker_image"] = docker_image
proj["docker_network_mode"] = "bridge_local_only"
proj["docker_auto_start_on_project_start"] = True
proj["docker_auto_stop_on_project_stop"] = True
proj["docker_workspace_mount_mode"] = "agent_territory_rw"
proj["docker_readonly_rootfs"] = False
proj["docker_cpu_limit"] = 1.0
proj["docker_memory_limit_mb"] = 512
req("POST", "/config/save", json=cfg).raise_for_status()

req("POST", f"/projects/{project_id}/start").raise_for_status()

msg = (
    "协作要求：先协商分工，再编码。跨代理调用统一用 HermesClient.route，"
    "协议条款先 contract-register/commit/resolve。实现必须是 Python 可运行代码。"
)
for aid in agents.keys():
    req("POST", "/confess", json={"agent_id": aid, "message": msg, "silent": False}).raise_for_status()

status = req("GET", f"/agents/status?project_id={project_id}").json()
print(json.dumps({"project_id": project_id, "agents_status": status.get("agents", [])}, ensure_ascii=False, indent=2))
PY

echo "==> Done."
