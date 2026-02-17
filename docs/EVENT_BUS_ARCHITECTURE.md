# EVENT BUS ARCHITECTURE

## 1. SSOT
- 统一事件主账本：`projects/{project_id}/runtime/events.jsonl`
- 文件锁：`projects/{project_id}/runtime/events.lock`

## 2. 核心模型
- `EventRecord`：统一事件结构（`event_id/project_id/domain/event_type/state/priority/payload/attempt/max_attempts/...`）
- `EventState`：`queued/picked/processing/done/failed/dead`（仅传输态）
- `EventHandler`：`on_pick/on_process/on_success/on_fail/on_dead`

## 3. 执行链路
1. API/Service 调 `gods.<domain>.facade` 产生事件。
2. 事件写入 `events.jsonl`。
3. Angelia worker 从总线 pick 事件。
4. worker 通过 `registry` 查找 handler 执行 `on_process`。
5. 状态推进统一走 `gods/events/store.py`。

## 4. 域事件映射
- Interaction: `interaction.message.sent/interaction.message.read/interaction.hermes.notice/interaction.detach.notice/interaction.agent.trigger`
- Iris: `mail_event/mail_deliver_event/mail_ack_event`
- Angelia: `timer_event/manual_event/system_event`
- Hermes: `hermes_protocol_invoked_event/hermes_job_updated_event/hermes_contract_*`
- Runtime(Detach): `detach_submitted_event/detach_started_event/detach_stopping_event/detach_stopped_event/detach_failed_event/detach_reconciled_event/detach_lost_event`

## 5. 约束
- 旧 `/angelia/events*` 与 `/projects/{project_id}/detach/*` 已移除。
- 新事件必须通过 `EventRecord + EventHandler`。
- 事件状态变更不得绕过 `gods/events/store.py`。
- EventBus payload 禁止承载业务状态字段（如 `delivered_at/handled_at/read_at/...`）。
