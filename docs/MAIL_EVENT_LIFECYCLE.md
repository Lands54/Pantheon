# MailEvent 生命周期（Iris 单一事件源）

## 目标
将消息与调度状态收敛到一个权威账本：`projects/{project_id}/runtime/events.jsonl`。

## 角色分工
1. Iris：事件主账本与状态迁移规则。
2. Angelia：调度执行（pick/process/requeue/dead）与 worker 生命周期。
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

## 状态机
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
3. worker `pick -> processing -> done/requeue/dead`。
4. 注入上下文时将 mail event 标为 `delivered`。
5. 脉冲完成后 `ack_handled` 标为 `handled`，同步 outbox receipt。

## 失败与恢复
1. 执行失败：`mark_mail_failed_or_requeue`，达到上限进入 `dead`。
2. 卡死恢复：`reclaim_stale_mail_processing`。
3. 人工重试：`retry_mail_event` 将 `failed/dead` 回到 `queued`。

## 兼容性
本次为 Breaking 变更：
1. API 与工具返回字段改为 `mail_event_id`、`wakeup_sent`。
2. 不再保证旧 `inbox_event_id` 字段。
