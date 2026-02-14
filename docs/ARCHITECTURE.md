# Gods Platform 架构概览（当前实现）

## 1. 总体结构

Gods Platform 采用三层结构：

- 核心引擎：`gods/`
- API 服务：`api/`
- 命令行：`cli/`

所有运行时世界数据都存放在 `projects/{project_id}/` 下，形成物理隔离。

## 2. 核心引擎（`gods/`）

### 2.1 Agent 模型

- `gods/agents/base.py`：`GodAgent`，每个 Agent 的主脉冲循环。
- `gods/agents/brain.py`：`GodBrain`，按项目+Agent 动态解析模型并调用 OpenRouter。
- `gods/workflow.py`：LangGraph 编排（公共讨论与私聊流程）+ SQLite checkpoint。
- `gods/state.py`：统一状态定义（`GodsState`）。

### 2.2 工具系统

- `gods/tools/communication.py`：私聊投递、收件箱读取、上行给人类、Synod 升级。
- `gods/tools/filesystem.py`：Agent 领地内文件读写与精确替换。
- `gods/tools/execution.py`：受限命令执行（黑名单+禁止复杂 shell 符号）。

### 2.3 配置与持久化

- `gods/config.py`：`config.json` 的加载、迁移、保存。
- `projects/{project_id}/memory.sqlite`：LangGraph checkpoint。
- `projects/{project_id}/agents/{agent_id}/memory.md`：可读记忆日志。

## 3. API 层（`api/`）

- `api/server.py`：FastAPI 入口、路由注册、后台 simulation loop。
- `api/routes/config.py`：配置读取/保存。
- `api/routes/projects.py`：项目增删。
- `api/routes/agents.py`：Agent 增删。
- `api/routes/communication.py`：
  - `/broadcast`：SSE 输出多 Agent 讨论流。
  - `/confess`：向指定 Agent 私聊并可触发即时 pulse（`silent=false`）。
  - `/prayers/check`：读取 Agent 发给人类的消息。

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
└── memory.sqlite
```

## 6. 数据流（关键路径）

1. 人类发起 `broadcast` 或 `confess`。  
2. API 构造 `GodsState`，调用 LangGraph 或直接触发 Agent pulse。  
3. Agent 先 `check_inbox`，再结合 `agent.md` + `memory.md` 进行推理。  
4. 工具调用结果写入消息流与记忆文件。  
5. `broadcast` 场景通过 SSE 实时返回客户端。  
