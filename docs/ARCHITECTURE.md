# Gods Platform 架构概览（当前实现）

> 最新模块职责、依赖关系与模块内部运行图请以 `docs/BACKEND_MODULES_RUNTIME_MAP.md` 为唯一事实源。

## 1. 总体结构

Gods Platform 采用三层结构：

- 核心引擎：`gods/`
- 用例服务层：`api/services/`
- API 服务：`api/`
- 命令行：`cli/`

所有运行时世界数据都存放在 `projects/{project_id}/` 下，形成物理隔离。

## 2. 核心引擎（`gods/`）

### 2.1 Agent 模型

- `gods/agents/base.py`：`GodAgent`，每个 Agent 的主脉冲循环。
- `gods/agents/brain.py`：`GodBrain`，按项目+Agent 动态解析模型并调用 OpenRouter。
- `gods/agents/phase_runtime/`：阶段运行时包（`core/policy/strategies`）。
- `gods/state.py`：统一状态定义（`GodsState`）。

### 2.2 工具系统

- `gods/tools/communication.py`：通信工具导出（实现拆分到 `comm_inbox/comm_human`）。
- `gods/tools/filesystem.py`：Agent 领地内文件读写与精确替换。
- `gods/tools/execution.py`：受限命令执行（黑名单+禁止复杂 shell 符号）。
- `gods/tools/hermes.py`：协议调用、路由、契约提交与端口租约。
- `gods/tools/mnemosyne.py`：Agent 档案持久化读写（agent vault）。

### 2.2.1 命令执行后端（`gods/runtime/`）

- `gods/runtime/execution_backend.py`：执行后端抽象（`local` / `docker`）。
- `gods/runtime/docker/*`：Agent 容器生命周期与执行管理。
- `run_command` 通过 backend resolver 路由，不再固定宿主机 subprocess。

### 2.2.2 Detach 后台托管（`gods/runtime/detach/`）

- `models.py`：后台任务状态模型（`queued/running/stopping/stopped/failed/lost`）。
- `store.py`：项目级 jobs/logs 落盘与文件锁。
- `policy.py`：FIFO 回收策略（project + agent 双上限）。
- `runner.py`：后台执行线程（基于 `docker exec`）与停止控制。
- `service.py`：submit/list/stop/reconcile/startup_lost 统一入口。
- 一期限制：仅 `command_executor=docker` 可用，local 后端明确拒绝。

### 2.3 统一事件总线（`gods/events` + `gods/iris` + `gods/angelia`）

- `gods/events/models.py`：统一 `EventRecord/EventState/EventEnvelope`。
- `gods/events/store.py`：`projects/{project_id}/runtime/events.jsonl` + `events.lock`（统一 SSOT）。
- `gods/events/handler.py` + `registry.py`：`EventHandler` 五阶段与注册表。
- `gods/iris`：Mail 语义与回执语义（`mail_event/mail_deliver_event/mail_ack_event`）。
- `gods/angelia`：调度执行与 worker 生命周期；worker 通过 `registry` 分发 `EventHandler`。
- `gods/angelia/pulse/*`：保留为兼容/策略资产，不再作为主事件链路存储。

### 2.4 Hermes 协议总线（`gods/hermes/`）

- `models.py`：协议/调用/任务模型定义。
- `registry.py`：项目级协议注册与检索（精确 `name + version`）。
- `schema.py`：请求/响应 schema 校验。
- `router.py`：provider 路由（支持 `agent_tool` 与 `http`，HTTP 目前限制为 localhost/127.0.0.1）。
- 安全默认：`agent_tool` provider 在项目级默认禁用，需显式开启 `hermes_allow_agent_tool_provider=true`。
- `executor.py`：sync/async 执行与审计落盘。
- `store.py`：项目级持久化（registry/invocations/jobs）。
- `limits.py`：协议级并发与速率限制。
- `contracts.py`：结构化契约注册、承诺、职责解析（default + agent-specific）。

### 2.5 配置与持久化

- `gods/config/*`：`config.json` 的模型、加载迁移、规范化与保存。
- `projects/{project_id}/memory.sqlite`：LangGraph checkpoint。
- `projects/{project_id}/mnemosyne/chronicles/{agent_id}.md`：可读记忆日志。
- `projects/{project_id}/runtime/events.jsonl`：统一事件总线单一事实源（Iris/Angelia/Hermes/Detach）。
- `projects/{project_id}/runtime/events.lock`：统一事件总线文件锁。
- `projects/{project_id}/runtime/pulse_events.jsonl`：兼容/诊断队列（非主执行链路）。
- `projects/{project_id}/runtime/detach_jobs.jsonl`：Detach 后台任务存储。
- `projects/{project_id}/runtime/detach_logs/{job_id}.log`：Detach 任务日志。
- `projects/{project_id}/runtime/locks/*.lock`：Inbox/Pulse 文件锁。
- `projects/{project_id}/protocols/registry.json`：Hermes 协议注册表。
- `projects/{project_id}/protocols/invocations.jsonl`：Hermes 调用审计日志。
- `projects/{project_id}/protocols/jobs/*.json`：Hermes 异步任务状态。
- `projects/{project_id}/mnemosyne/*`：Mnemosyne 档案层（agent/human/system vault）。
- `projects/{project_id}/runtime/ports.json`：Hermes 端口租约。

## 3. API 层（`api/`）

- `api/app.py`：FastAPI 应用装配入口（路由注册、生命周期挂载）。
- `api/routes/config.py`：配置读取/保存（密钥脱敏输出）。
- `api/routes/projects.py`：项目增删。
- `api/routes/projects.py`：项目增删 + 项目报告生成/查询（`/projects/{project_id}/report/*`）。
- `api/routes/projects.py`：运行时容器接口：
  - `GET /projects/{project_id}/runtime/agents`
  - `POST /projects/{project_id}/runtime/agents/{agent_id}/restart`
  - `POST /projects/{project_id}/runtime/reconcile`
- `api/routes/events.py`：统一事件接口：
  - `POST /events/submit`
  - `GET /events`
  - `POST /events/{event_id}/retry`
  - `POST /events/{event_id}/ack`
  - `POST /events/reconcile`
  - `GET /events/metrics`
- `api/routes/angelia.py`：仅保留 agent/supervisor 相关接口；旧 `/angelia/events*` 已下线（410）。
- `api/routes/projects.py`：旧 `/projects/{project_id}/detach/*` 任务接口已下线（410），统一走 `/events/*`。
- `api/routes/agents.py`：Agent 增删。
- `api/routes/hermes.py`：协议注册、调用、任务查询、审计查询。
  - 额外支持：`/hermes/route`（按 `target_agent + function_id` 路由调用）
  - 额外支持：`/hermes/contracts/*`（契约注册/承诺/解析）
  - 额外支持：`/hermes/ports/*`（项目级端口租约 reserve/release/list）
- `api/routes/mnemosyne.py`：Mnemosyne 档案写入/查询/读取。
- `api/routes/communication.py`：
  - `/confess`：向指定 Agent 私聊并写入 `mail_event`；默认同时发送 worker wakeup（`silent=false`）。

## 3.5 服务层（`api/services/`）

- `api/services/config_service.py`：配置脱敏读取、配置保存编排。
- `api/services/project_service.py`：项目生命周期、知识图谱重建、Project 报告编排。
- `api/services/simulation_service.py`：调度循环与 startup 安全暂停策略。
- `api/services/*`：统一调用 `gods.<domain>.facade`，不直连域内 `store/policy/models/...`。

说明：`api/routes/*` 只做协议适配，业务逻辑下沉到 service，避免 API 膨胀。

## 4. CLI 层（`cli/`）

- 入口：`cli/main.py`
- 快速启动脚本：`temple.sh`
- 子命令：
  - 项目管理：`project list/create/switch/delete`
  - Agent 管理：`list/activate/deactivate/agent view|edit`
  - 通信：`confess`
  - 配置：`config show/set/models`
  - 事件调试：`angelia events/enqueue`、`inbox outbox`
  - 后台任务：`detach submit/list/stop/logs`

## 5. 多项目隔离模型

每个项目目录结构：

```text
projects/{project_id}/
├── agents/{agent_id}/
│   └── runtime_state.json
├── mnemosyne/
│   ├── agent_profiles/{agent_id}.md
│   ├── chronicles/{agent_id}.md
│   └── {agent|human|system}/
├── runtime/
│   ├── mail_events.jsonl
│   ├── pulse_events.jsonl
│   ├── detach_jobs.jsonl
│   ├── detach_logs/{job_id}.log
│   └── locks/*.lock
├── protocols/
│   ├── registry.json
│   ├── invocations.jsonl
│   └── jobs/{job_id}.json
└── memory.sqlite
```

## 6. 数据流（关键路径）

1. 人类/Agent 发送私信 -> 写入 `events.jsonl`（`domain=iris,event_type=mail_event,state=queued`）。  
2. Angelia 仅通过 mailbox `notify/wait` 做快速唤醒，不再维护独立主事件账本。  
3. worker 从统一事件总线执行 pick/process/done/requeue/dead。  
4. pulse 期间批量注入可投递 mail event，并将其推进到 `delivered/handled`。  
5. 失败事件按重试策略回退或进入 dead-letter；Agent 记忆持续写入 `mnemosyne/chronicles/{agent_id}.md`。  
