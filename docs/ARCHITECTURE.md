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

### 2.3 Iris + Angelia Pulse 事件模块（`gods/iris` + `gods/angelia/pulse`）

- `gods/iris/models.py`：Iris(Inbox) 事件与 4 态（`pending/delivered/deferred/handled`）。
- `gods/iris/store.py`：`projects/{project_id}/runtime/inbox_events.jsonl` 读写与状态迁移（文件锁）。
- `gods/iris/service.py`：消息入队、批量注入、handled 回执。
- `gods/angelia/pulse/models.py`：Pulse 事件（`inbox_event/timer/manual/system`）与状态。
- `gods/angelia/pulse/queue.py`：`projects/{project_id}/runtime/pulse_events.jsonl` 队列、优先级出队、去重。
- `gods/angelia/pulse/policy.py`：空队列保底心跳与注入预算策略（配置驱动）。
- `gods/angelia/pulse/scheduler_hooks.py`：调度前注入与 `after_action` 软打断注入。

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
- `projects/{project_id}/runtime/inbox_events.jsonl`：Inbox 事件存储。
- `projects/{project_id}/runtime/pulse_events.jsonl`：Pulse 队列存储。
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
- `api/routes/projects.py`：Detach 后台任务接口：
  - `POST /projects/{project_id}/detach/submit`
  - `GET /projects/{project_id}/detach/jobs`
  - `POST /projects/{project_id}/detach/jobs/{job_id}/stop`
  - `POST /projects/{project_id}/detach/reconcile`
  - `GET /projects/{project_id}/detach/jobs/{job_id}/logs`
- `api/routes/angelia.py`：Angelia 单轨调度接口：
  - `GET /angelia/events`
  - `POST /angelia/events/enqueue`
  - `GET /angelia/agents/status`
- `api/routes/agents.py`：Agent 增删。
- `api/routes/hermes.py`：协议注册、调用、任务查询、审计查询。
  - 额外支持：`/hermes/route`（按 `target_agent + function_id` 路由调用）
  - 额外支持：`/hermes/contracts/*`（契约注册/承诺/解析）
  - 额外支持：`/hermes/ports/*`（项目级端口租约 reserve/release/list）
- `api/routes/mnemosyne.py`：Mnemosyne 档案写入/查询/读取。
- `api/routes/communication.py`：
  - `/confess`：向指定 Agent 私聊并写入 Inbox Event；默认同时入队 `inbox_event` wake（`silent=false`）。

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
│   ├── inbox_events.jsonl
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

1. 人类/Agent 发送私信 -> 写入 `inbox_events.jsonl`（`pending`）。  
2. 同步写入 `pulse_events.jsonl`（`inbox_event`，高优先级）。  
3. 调度器优先消费 Pulse 队列；空队列时按 `queue_idle_heartbeat_sec` 注入 `timer` pulse。  
4. pulse 开始前注入 Inbox 事件；工具返回后执行 `after_action` 软打断探针。  
5. pulse 完成后将已注入消息标记为 `handled`；Agent 记忆持续写入 `mnemosyne/chronicles/{agent_id}.md`。  
