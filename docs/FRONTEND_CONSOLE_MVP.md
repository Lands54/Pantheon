# Frontend Console MVP 设计与约束

## 1. 目标

在不新增后端 API 的前提下，提供可用的前端控制台，覆盖：

1. 项目与 Agent 状态总览
2. 事件队列观测与重试
3. 人类消息发送（interaction 事件）
4. Agent 工作记忆视图（Janus + Iris）
5. 项目核心控制（create/start/stop）

## 2. 页面与数据源

## 2.1 Dashboard

- 数据：`GET /agents/status`、Agent SSE `GET /agents/status/stream`、Hermes SSE `GET /hermes/events`
- 能力：
  1. 查看 agent 运行态
  2. 查看 Hermes 实时事件
  3. 展示 SSE 降级状态（fallback 轮询）

## 2.2 Events

- 数据：`GET /events`、Events SSE `GET /events/stream`
- 操作：
  1. `POST /events/{event_id}/retry`
  2. `POST /events/{event_id}/ack`
- 过滤：`project_id/domain/event_type/state/agent_id/limit`

## 2.3 Message Center

- 操作：`POST /events/submit`
- 固定语义：
  1. `domain=interaction`
  2. `event_type=interaction.message.sent`
  3. 默认 `sender_id=human.overseer`

## 2.4 Agent Detail

- Live Context：
  1. `GET /projects/{project_id}/context/preview`
  2. `GET /projects/{project_id}/context/reports`
- Inbox/Outbox：
  1. `GET /projects/{project_id}/inbox/outbox`
- Recent Events：
  1. `GET /events?agent_id=...`

## 2.5 Project Control

- 操作：
  1. `POST /projects/create`
  2. `POST /projects/{project_id}/start`
  3. `POST /projects/{project_id}/stop`

## 3. 前端目录约束

`frontend/src/` 采用模块化目录：

1. `api/`：请求封装与接口映射
2. `hooks/`：轮询与实时流
3. `store/`：全局状态（当前项目、配置、加载状态）
4. `pages/`：页面级容器
5. `components/`：复用组件
6. `types/`：数据形状定义

## 4. 运行时策略

1. 混合实时：SSE + 轮询兜底
2. Events 与 Agent Status 优先使用 SSE 快照流，被动更新为主
3. SSE 断开时继续轮询关键数据
4. 任何错误不导致页面崩溃，最多降级为只读刷新

## 5. 禁行项

1. 禁止调用已下线接口：`/broadcast`、`/prayers/check`、`/confess`
2. 禁止在前端实现多人类权限逻辑（本轮不做 auth）
3. 禁止新增与后端不一致的字段别名

## 6. 手动验收清单

1. 切换项目后，Dashboard/Events/Agent Detail 数据全部切到新项目
2. Message Center 发送后，可在 Events 与 outbox 回执看到记录
3. Agent Detail 可以看到 context preview/reports
4. Events retry 后状态变化可见
5. 移动端布局可滚动、可操作，不出现主区域不可见
