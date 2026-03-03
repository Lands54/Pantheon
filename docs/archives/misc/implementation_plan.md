# 分布式 Agent 系统开发计划 (Implementation Plan)

## 0. 目标
实现一个文件夹隔离的自动化 Agent 系统，支持 Agent 编写程序、操作私有文件及跨 Agent 通信。

## 1. 核心组件开发

### 1.1 `Platform Core` (Python 实现)
- **Registry**: 扫描 `agents/` 目录，加载所有 `mnemosyne/agent_profiles/{agent}.md`。
- **Message Bus**: 实现 `agents/{id}/.agent/inbox.jsonl` 作为消息接收端。
- **Call Parser**: 正则解析 `[[...]]` 格式的指令。

### 1.2 `Agent Runtime`
- 为每个 Agent 提供一个上下文管理器，限制其 `file_ops` 只能在 `agents/{id}/` 路径下执行。
- 支持执行 `agents/{id}/workspace/` 下的代码。

### 1.3 `Communication Interface`
- `send_message(from, to, content)`
- `broadcast_message(from, group, content)`

## 2. 交互逻辑
1. **监听**: 平台监听每个 Agent 的 `workspace` 变动或 agent profile 状态更新。
2. **触发**: 检测到 `[[call]]` 时，平台接管并执行路由。
3. **反馈**: 平台将结果写入 Agent 的 `inbox` 或 `mnemosyne/chronicles/{agent}.md`。

## 3. 具体任务清单 (Phase 1)
- [ ] 编写 `platform/registry.py`: 扫描并注册 Agent。
- [ ] 编写 `platform/bus.py`: 消息存储与分发逻辑。
- [ ] 编写 `platform/parser.py`: 指令解析器。
- [ ] 编写 `platform/main.py`: 系统主循环。
