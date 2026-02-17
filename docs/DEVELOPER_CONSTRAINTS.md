# 开发约束总规范（vNext）

本文档是后续开发者的强约束入口，覆盖模块边界、事件链路、人类身份语义与 CLI 观测方式。

## 1. 唯一交互范式

所有与 Agent 的交互控制流必须遵守：

`Module -> Event -> Handler -> Module -> (可选)Event`

禁止：
1. LLM 直接写业务存储。
2. 跨模块直改对方内部文件/存储。
3. 新增旧链路兼容层（legacy alias/bridge）。

## 2. 人类与 Agent 语义

1. 人类身份固定：`human.overseer`。
2. 人类在协议语义上是特殊 agent（可收发消息）。
3. 人类不是调度 worker，不持有独立 Angelia 队列线程。
4. 人类侧可以直接使用系统查询 API/CLI 获取全局状态，不必经事件通知。

## 3. 事件与状态机边界

1. EventBus（`gods/events`）只承载传输态：`queued/picked/processing/done/failed/dead`。
2. 业务状态机归属各域：
   - Iris：mailbox/回执/已读
   - Hermes：契约与协议业务态
   - Detach：后台任务业务态
3. 禁止把业务态字段写入 EventBus（如 `handled_at/read_at/...`）。

## 4. 模块调用边界（必须）

1. `api/routes -> api/services -> gods.<domain>.facade`。
2. `gods` 域间调用默认走对方 `facade`。
3. `gods/hermes/*` 禁止直连 `gods.iris.facade.enqueue_message`。
4. Tool 发消息必须走 interaction 事件，不允许直调 Iris 入箱。

## 5. Agent 交互入口规范

推荐入口：
1. `POST /events/submit`（`domain=interaction`）
2. CLI：`./temple.sh msg send ...`

已下线：
1. `/confess`
2. `send_to_human` 旧工具路径

## 6. CLI 观测规范（你问的“显示每个 agent”）

有，标准命令如下：

```bash
# 显示当前项目所有 agent 运行状态
./temple.sh agent status

# 仅看一个 agent
./temple.sh agent status --agent-id <agent_id>

# JSON 输出（用于脚本/自动化）
./temple.sh agent status --json
```

补充：
1. `config show` 仅看配置，不再承载 agent 运行态。
2. 事件排查使用 `./temple.sh events list ...`。

## 7. 工具策略约束

1. `check_inbox/check_outbox` 默认禁用（仅 debug/audit 场景显式开启）。
2. 变更工具可见性统一走配置：
   - `agent.<id>.disable_tool`
   - `agent.<id>.enable_tool`
   - `agent.<id>.disabled_tools`

## 8. 新功能开发清单（必走）

新增任何 Agent 相关能力时，必须同时完成：

1. 事件类型定义（`interaction` 或对应 domain）
2. handler 落地（`on_process` 仅调 facade/tool）
3. API/service 路由接入（不得绕过）
4. 边界脚本绿：
   - `check_import_cycles`
   - `check_call_boundaries`
   - `check_no_legacy_paths`
   - `check_event_bus_integrity`
5. 测试补齐（单元 + 集成）
6. 文档更新（至少本文件 + 相关模块文档）

## 9. 参考文档

1. `docs/AGENT_EVENT_INTERACTION_PROTOCOL.md`
2. `docs/CALL_BOUNDARY_RULES.md`
3. `docs/EVENT_BUS_ARCHITECTURE.md`
4. `docs/CLI_MANUAL.md`
