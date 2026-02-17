# Gods CLI 手册

本文档描述当前版本 `temple.sh` 的命令结构与推荐用法。

## 1. 设计原则

1. 命令按职责分组：`project/agent/msg/events/config/...`
2. Agent 交互统一事件化：发送消息优先使用 `msg send` 或 `events submit`
3. 系统控制面保持直调：`project start/stop/reconcile`、`config show/set/save`

## 2. 快速开始

```bash
# 初始化 API Key
./temple.sh init <OPENROUTER_API_KEY>

# 查看项目
./temple.sh project list

# 查看 Agent 列表与状态
./temple.sh agent list
./temple.sh agent status

# 人类向 Agent 发消息（推荐）
./temple.sh msg send --to genesis --title "任务" --content "先检查 inbox"
```

## 3. 命令总览

### 3.1 project

项目生命周期与运维命令。

```bash
./temple.sh project list
./temple.sh project create <project_id>
./temple.sh project switch <project_id>
./temple.sh project delete <project_id>
./temple.sh project start <project_id>
./temple.sh project stop <project_id>
./temple.sh project report <project_id>
./temple.sh project report-show <project_id>
```

### 3.2 agent

Agent 管理与运行状态命令。

```bash
./temple.sh agent list
./temple.sh agent create <agent_id> --directives "..."
./temple.sh agent delete <agent_id>
./temple.sh agent activate <agent_id>
./temple.sh agent deactivate <agent_id>
./temple.sh agent status
./temple.sh agent status --agent-id <agent_id>
./temple.sh agent status --json
./temple.sh agent view <agent_id>
./temple.sh agent edit <agent_id>
```

说明：
1. `agent status` 是调度/运行状态标准入口。
2. `config show` 不再承载 agent 运行态详情。

### 3.3 msg

面向人类的消息命令，内部自动转成 interaction 事件。

```bash
./temple.sh msg send \
  --to genesis \
  --title "任务指令" \
  --content "请先处理 inbox 再汇报" \
  --msg-type confession
```

常用参数：
1. `--sender` 默认 `human.overseer`
2. `--no-pulse` 不触发立即唤醒
3. `--max-attempts` 事件最大重试次数

### 3.4 events

事件总线底层命令（专家模式）。

```bash
./temple.sh events submit --domain interaction --type interaction.message.sent --payload '{"to_id":"genesis","sender_id":"human.overseer","title":"任务","content":"...","msg_type":"confession","trigger_pulse":true}'
./temple.sh events list --domain interaction --type interaction.message.sent --limit 20
./temple.sh events retry <event_id>
./temple.sh events ack <event_id>
./temple.sh events reconcile --timeout-sec 60
```

### 3.5 config

配置查看与设置。

```bash
./temple.sh config show
./temple.sh config models
./temple.sh config set <key> <value>
./temple.sh config check-memory-policy
```

### 3.6 其他命令组

```bash
./temple.sh doctor
./temple.sh doctor -p <project_id>
./temple.sh doctor -p <project_id> --strict
./temple.sh protocol ...
./temple.sh mnemosyne ...
./temple.sh runtime ...
./temple.sh detach ...
./temple.sh context ...
./temple.sh inbox ...
./temple.sh angelia ...
./temple.sh check <agent_id>
./temple.sh test --cleanup
```

`doctor` 说明：
1. 自动修复项目基础结构、`memory_policy` 字段与缺失规则。
2. 自动降级“开启 chronicle 但无模板”的规则为仅 runtime_log，并打印修复明细。
3. 默认执行守门检查：`check_import_cycles`、`check_call_boundaries`、`check_no_legacy_paths`、`check_event_bus_integrity`。
4. 默认“运行优先”：守门失败记为告警；加 `--strict` 时改为阻断失败。

## 4. 推荐操作流程

### 4.1 创建项目并启动

```bash
./temple.sh project create demo_world
./temple.sh project switch demo_world
./temple.sh project start demo_world
```

### 4.2 创建并激活 Agent

```bash
./temple.sh agent create genesis --directives "# GENESIS\n你是总协调者。"
./temple.sh agent activate genesis
./temple.sh agent status --agent-id genesis
```

### 4.3 人类发消息给 Agent

```bash
./temple.sh msg send --to genesis --title "首个任务" --content "先查看 inbox 并开始执行"
```

### 4.4 观测回执与事件

```bash
./temple.sh inbox outbox --agent human.overseer --to genesis --limit 20
./temple.sh events list --domain interaction --agent genesis --limit 20
```

## 5. 旧命令迁移

1. `./temple.sh list` -> `./temple.sh agent list`
2. `./temple.sh activate <id>` -> `./temple.sh agent activate <id>`
3. `./temple.sh deactivate <id>` -> `./temple.sh agent deactivate <id>`
4. `/confess` API 与旧 communication 入口已下线，请改用 `events submit` 或 `msg send`

## 6. 常见问题

### 6.1 `msg send` 和 `events submit` 有什么区别

1. `msg send`：人类友好封装，参数更直观。
2. `events submit`：底层通用接口，适合脚本化与高级用法。

### 6.2 为什么 `config show` 看不到 agent 调度细节

因为职责已收口，agent 运行态统一通过：

```bash
./temple.sh agent status
```

### 6.3 如何查看某个事件失败原因

```bash
./temple.sh events list --state failed --limit 50
```

再根据 `event_id` 执行：

```bash
./temple.sh events retry <event_id>
```

## 7. 与前端控制台对照

1. `agent status` 对应前端 `Dashboard` 的 Agent 状态卡片/表。
2. `events list/retry/ack` 对应前端 `Events` 页的筛选与操作。
3. `msg send` 对应前端 `Message Center` 的发送面板。
4. `projects/{id}/context/*` 与 `inbox/outbox` 对应前端 `Agent Detail` 的工作记忆视图。
