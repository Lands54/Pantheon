# ISSUE: Synod Escalation Orchestration Gap

## Date
2026-02-14

## Context
在当前架构中，Agent 可以调用 `post_to_synod` 发出升级信号，但自治调度路径尚未把该信号自动编排到公开公议执行链路。

## Current Behavior
1. Agent 调用 `post_to_synod` 后，`next_step` 置为 `escalated`。
2. Scheduler 仅记录 `last_next_step=escalated`，没有后续自动分派。
3. 公开公议执行（`/broadcast` SSE + workflow/sqlite）在 legacy social 路径，且默认关闭。

## Expected Behavior
当 Agent 发出 `post_to_synod`：
1. 上层应捕获 `escalated` 事件。
2. 根据策略决定是否自动触发 Synod（例如调用内部 broadcast orchestrator）。
3. 将 Synod 结果回灌到相关 Agent 的后续任务上下文。

## Proposed Design (Future)
- 在 scheduler 增加 escalation event queue。
- 引入 escalation policy（按项目配置：自动/人工/静默）。
- 若启用 legacy social API：桥接到 `/broadcast`。
- 若禁用 legacy：提供核心内置 synod executor（无 SSE）以保持自治闭环。

## Priority
Medium (当前阶段先聚焦单 Agent，后续再实现)
