# Temple CLI 入门操作指南 (CLI Guide)

`temple.sh` (内部调用 `cli/main.py`) 是与 Gods Platform 进行交互的主命令行接入口。它负责管理项目（Worlds）、代理（Agents）、统一通信与调度总线，并提供所有组件的调试接口。

## ⚙️ 基本用法

所有的操作都在根目录使用 `./temple.sh` 执行：

```bash
./temple.sh [全局参数] <主命令> <子命令> [参数...]
```

**全局参数**：

- `--project, -p <project_id>`：临时指定运行操作的目标项目名称，而非使用系统默认选中的活跃项目。

---

## 🌍 1. 项目管理 (Worlds/Projects)

管理运行中的沙盒世界与相关的图谱层。

- **创建世界**：`./temple.sh project create <project_id>`
- **列出所有世界**：`./temple.sh project list`
- **切换当前活跃世界**：`./temple.sh project switch <project_id>`
- **开/关世界引擎**：
  - `./temple.sh project start <project_id>` (互斥启动，独占引擎)
  - `./temple.sh project stop <project_id>`
- **构建世界报告**：`./temple.sh project report <project_id>` (构建后将存入 Mnemosyne 档案)
- **社会图谱**：
  - `./temple.sh project social-graph <project_id>`
  - `./temple.sh project social-edge <project_id> --from-id <A> --to-id <B> --allow <true/false>`

---

## 🤖 2. 代理管理 (Agents)

沙盒内居民的管理与状态观测。

- **查看所有 Agent**：`./temple.sh agent list`
- **创建 Agent**：`./temple.sh agent create <agent_id> --directives "<性格/能力指引>"`
- **查看 Agent 激活/调度状态**：`./temple.sh agent status`
- **查看 Agent 设定**：`./temple.sh agent view <agent_id>`
- **修改执行策略 (Strategy)**：
  - `/temple.sh agent strategy set --agent <agent_id> --strategy react_graph` (或 `freeform`)

---

## 📩 3. 消息与交互 (Communication)

这是给人类提供的人格化快速通信工具，内部将被转换为 `interaction` Event。

- **发送信件 (人类给 Agent)**：
  ```bash
  ./temple.sh msg send --to <agent_id> --title "你的任务" --content "请分析目录下的日志并提交报告。"
  ```

---

## ⚡ 4. 统一事件总线调度 (Events / Angelia)

Gods Platform 采用基于 Pulse (心跳脉冲) 的严格事件执行队列。

- **查看事件队列**：`./temple.sh events list`
- **排查某个 Agent 的死信/失败事件**：`./temple.sh events list --state err`
- **重试事件**：`./temple.sh events retry <event_id>`
- **手动丢弃/确认事件**：`./temple.sh events ack <event_id>`

> 💡 _Angelia 命令别名_：`events` 主要用于统一总线的语义操作，而 `./temple.sh angelia target_agent --type manual` 可用于直接对单一 Agent 发起手动空脉冲以唤醒该 Agent。

---

## 🤝 5. Hermes 协议与契约 (Protocols / Contracts)

Agent-to-Agent 间的 API 调用接口控制。

- **注册/承诺 API 契约**：
  - `./temple.sh protocol contract-register --file api.json`
  - `./temple.sh protocol contract-commit --title "XX API" --version "1.0.0" --agent <agent_id>`
- **查看契约列表表**：`./temple.sh protocol contract-list`
- **发起模拟协议调用 (Debug)**：
  - `./temple.sh protocol call --name my_api.func --caller root --payload '{"x": 1}'`
- **查看调用审计日志**：`./temple.sh protocol history`
- **创建协议模板**：`./temple.sh protocol clause-template --id "xxx"`

---

## 🧠 6. 记忆档案层 (Mnemosyne / Context)

对 LLM 对话上下文、历史长程归档进行直接探查。

- **归档记忆层**：
  - `./temple.sh mnemosyne list --vault human`
  - `./temple.sh mnemosyne read <entry_id>`
- **运行时上下文穿透 (Janus Context)**：
  - **预览 Prompt 上下文**: `./temple.sh context preview <agent_id>` (查看下次触发心跳时，即将被注入给 LLM 的具体文本)
  - **查看 Pulse 执行帧记录**: `./temple.sh context pulse list <agent_id>`
  - **审查单帧(包含工具调用)**: `./temple.sh context pulse inspect <agent_id> <pulse_id>`

---

## 🐋 7. 运行时系统 (Runtime / Detach)

用于 Debug Docker Sandbox 的健康度。

- **运行状态**：`./temple.sh runtime status`
- **重置 Sandbox**：`./temple.sh runtime restart <agent_id>`
- **后台托管任务流监控**：
  - `./temple.sh detach list` (查看挂起的异步后台系统脚本)
  - `./temple.sh detach logs <job_id>`

---

## 🔧 8. 常见高频调试组合流

### 场景 A：创建项目并初始化角色

```bash
./temple.sh project create demo_world
./temple.sh project switch demo_world
./temple.sh agent create bot_alpha --directives "You are a pure python developer."
./temple.sh project start demo_world
```

### 场景 B：测试任务派发并排障

```bash
# 下发开发指令
./temple.sh msg send --to bot_alpha --title "New Task" --content "Write a binary search script in python."

# 查看 Agent 状态是否进入活跃运转状态（运行了多少 Token）
./temple.sh agent status

# 查看它在想什么（LLM Context）
./temple.sh context preview bot_alpha

# 如果卡死，查看是否处于事件报错/拒绝执行
./temple.sh events list --state failed
```
