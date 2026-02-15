# Gods Platform 架构概览（当前实现）

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
- `gods/workflow.py`：LangGraph 编排（公共讨论与私聊流程）+ SQLite checkpoint。
- `gods/state.py`：统一状态定义（`GodsState`）。

### 2.2 工具系统

- `gods/tools/communication.py`：通信工具兼容导出（实现拆分到 `comm_inbox/comm_human/comm_protocol`）。
- `gods/tools/filesystem.py`：Agent 领地内文件读写与精确替换。
- `gods/tools/execution.py`：受限命令执行（黑名单+禁止复杂 shell 符号）。
- `gods/tools/hermes.py`：协议注册、协议调用、异步任务查询、协议列表。
- `gods/tools/mnemosyne.py`：Agent 档案持久化读写（agent vault）。

### 2.3 Hermes 协议总线（`gods/hermes/`）

- `models.py`：协议/调用/任务模型定义。
- `registry.py`：项目级协议注册与检索（精确 `name + version`）。
- `schema.py`：请求/响应 schema 校验。
- `router.py`：provider 路由（支持 `agent_tool` 与 `http`，HTTP 目前限制为 localhost/127.0.0.1）。
- 安全默认：`agent_tool` provider 在项目级默认禁用，需显式开启 `hermes_allow_agent_tool_provider=true`。
- `executor.py`：sync/async 执行与审计落盘。
- `store.py`：项目级持久化（registry/invocations/jobs）。
- `limits.py`：协议级并发与速率限制。
- `contracts.py`：结构化契约注册、承诺、职责解析（default + agent-specific）。

### 2.4 配置与持久化

- `gods/config.py`：`config.json` 的加载、迁移、保存。
- `projects/{project_id}/memory.sqlite`：LangGraph checkpoint。
- `projects/{project_id}/agents/{agent_id}/memory.md`：可读记忆日志。
- `projects/{project_id}/protocols/registry.json`：Hermes 协议注册表。
- `projects/{project_id}/protocols/invocations.jsonl`：Hermes 调用审计日志。
- `projects/{project_id}/protocols/jobs/*.json`：Hermes 异步任务状态。
- `projects/{project_id}/mnemosyne/*`：Mnemosyne 档案层（agent/human/system vault）。
- `projects/{project_id}/runtime/ports.json`：Hermes 端口租约。

## 3. API 层（`api/`）

- `api/app.py`：FastAPI 应用装配入口（路由注册、生命周期挂载）。
- `api/server.py`：兼容包装层（保留旧导入，不承载业务）。
- `api/routes/config.py`：配置读取/保存（密钥脱敏输出）。
- `api/routes/projects.py`：项目增删。
- `api/routes/projects.py`：项目增删 + 项目报告生成/查询（`/projects/{project_id}/report/*`）。
- `api/routes/agents.py`：Agent 增删。
- `api/routes/hermes.py`：协议注册、调用、任务查询、审计查询。
  - 额外支持：`/hermes/route`（按 `target_agent + function_id` 路由调用）
  - 额外支持：`/hermes/contracts/*`（契约注册/承诺/解析）
  - 额外支持：`/hermes/ports/*`（项目级端口租约 reserve/release/list）
- `api/routes/mnemosyne.py`：Mnemosyne 档案写入/查询/读取。
- `api/routes/communication.py`：
  - `/broadcast`：SSE 输出多 Agent 讨论流。
  - `/confess`：向指定 Agent 私聊并可触发即时 pulse（`silent=false`）。
  - `/prayers/check`：读取 Agent 发给人类的消息。

## 3.5 服务层（`api/services/`）

- `api/services/config_service.py`：配置脱敏读取、配置保存编排。
- `api/services/project_service.py`：项目生命周期、知识图谱重建、Project 报告编排。
- `api/services/simulation_service.py`：调度循环与 startup 安全暂停策略。

说明：`api/routes/*` 只做协议适配，业务逻辑下沉到 service，避免 API 膨胀。

## 4. CLI 层（`cli/`）

- 入口：`cli/main.py`
- 快速启动脚本：`temple.sh`
- 子命令：
  - 项目管理：`project list/create/switch/delete`
  - Agent 管理：`list/activate/deactivate/agent view|edit`
  - 通信：`broadcast/confess/prayers/check`
  - 配置：`config show/set/models`

## 5. 多项目隔离模型

每个项目目录结构：

```text
projects/{project_id}/
├── agents/{agent_id}/
│   ├── agent.md
│   └── memory.md
├── buffers/
│   ├── {agent_id}.jsonl
│   ├── {agent_id}_read.jsonl
│   └── human.jsonl
├── protocols/
│   ├── registry.json
│   ├── invocations.jsonl
│   └── jobs/{job_id}.json
└── memory.sqlite
```

## 6. 数据流（关键路径）

1. 人类发起 `broadcast` 或 `confess`。  
2. API 构造 `GodsState`，调用 LangGraph 或直接触发 Agent pulse。  
3. Agent 先 `check_inbox`，再结合 `agent.md` + `memory.md` 进行推理。  
4. 工具调用结果写入消息流与记忆文件。  
5. `broadcast` 场景通过 SSE 实时返回客户端。  
