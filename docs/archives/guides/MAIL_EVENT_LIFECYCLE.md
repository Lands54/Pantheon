# MailEvent 生命周期（Iris Mailbox SSOT）

## 目标
将消息业务状态收敛到 Iris Mailbox 状态机；`events.jsonl` 仅作为调度传输总线。

## 角色分工
1. Iris：Mailbox 主账本与消息状态迁移规则（`queued/delivered/handled/...`）。
2. Angelia：调度执行（pick/process/done/requeue/dead）与 worker 生命周期。
3. Mailbox：仅用于 `notify/wait` 唤醒，不承载状态语义。

## 事件字段（核心）
1. `event_id`
2. `project_id`
3. `agent_id`
4. `event_type`
5. `priority`
6. `state`
7. `payload`
8. `sender/title/content/msg_type`
9. `attempt/max_attempts`
10. `dedupe_key`
11. `created_at/available_at/picked_at/delivered_at/handled_at/done_at`
12. `error_code/error_message`
13. `meta`

## Mailbox 状态机
1. `queued`
2. `picked`
3. `processing`
4. `delivered`
5. `handled`
6. `done`
7. `deferred`
8. `failed`
9. `dead`

## 主链路
1. `enqueue_message` 创建 `mail_event`（`queued`）。
2. 发送唤醒信号 `mailbox.notify`。
3. worker 在 EventBus 上执行 `pick -> processing -> done/requeue/dead`（传输态）。
4. 注入上下文时由 Iris 将 message 标为 `delivered`。
5. 脉冲完成后 `ack_handled` 标为 `handled`，同步 outbox receipt。

## 失败与恢复
1. 传输失败：EventBus 走 `failed/dead` 重试或死信。
2. Mailbox 状态只在 Iris 内推进，不与 EventBus 状态混写。

## Breaking 变更
本次为零兼容改造：
1. API 与工具返回字段改为 `mail_event_id`、`wakeup_sent`。
2. 不再保证旧 `inbox_event_id` 字段。
