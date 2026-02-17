# Detach Runtime（一期）

## 概述

Detach 是 `run_command` 之外的后台托管能力，目标是给 Agent 提供受控的长任务执行。

一期边界：

- 仅支持 `command_executor=docker`。
- 不做重启恢复；服务重启后历史未终态任务标记为 `lost`。
- 限流策略为 `Agent + Project` 双上限，超限按 FIFO 回收。

## 存储

- 事件主账本：`projects/{project_id}/runtime/events.jsonl`
- 任务运行态：`projects/{project_id}/runtime/detach_jobs.jsonl`
- 任务日志：`projects/{project_id}/runtime/detach_logs/{job_id}.log`
- 任务锁：`projects/{project_id}/runtime/locks/detach_jobs.lock`

## 状态机

- `queued`
- `running`
- `stopping`
- `stopped`
- `failed`
- `lost`

## 配置（ProjectConfig）

- `detach_enabled`
- `detach_max_running_per_agent`
- `detach_max_running_per_project`
- `detach_queue_max_per_agent`
- `detach_ttl_sec`
- `detach_stop_grace_sec`
- `detach_log_tail_chars`

## 接口

API:

- `POST /events/submit` (`domain=runtime,event_type=detach_submitted_event`)
- `GET /events` (`domain=runtime`)
- `POST /events/submit` (`domain=runtime,event_type=detach_stopping_event`)
- `POST /events/reconcile`

CLI:

- `./temple.sh -p <project> detach submit <agent> --cmd "..." `
- `./temple.sh -p <project> detach list [--agent ...] [--status ...]`
- `./temple.sh -p <project> detach stop <job_id>`
- `./temple.sh -p <project> detach logs <job_id>`
