# MIGRATION EVENTS BREAKING CHANGES

## 生效版本
- vNext 统一事件总线改造（一次切换，不保留旧兼容）。

## 1. API Breaking
- 新：`/events/submit` `/events` `/events/{event_id}/retry` `/events/{event_id}/ack` `/events/reconcile` `/events/metrics`
- 旧：`/angelia/events*` 已移除
- 旧：`/projects/{project_id}/detach/*` 已移除

## 2. 存储 Breaking
- 新 SSOT：`projects/{project_id}/runtime/events.jsonl`
- 零兼容：不提供迁移脚本、不做自动迁移
- 若检测到旧事件文件，启动直接失败并要求人工清理

## 3. 开发 Breaking
- 新事件必须使用 `EventRecord + EventHandler`。
- 禁止新增旁路事件存储。
- 状态推进必须走 `gods/events/store.py`。

## 4. 运维门禁
- `python scripts/check_import_cycles.py`
- `python scripts/check_call_boundaries.py`
- `python scripts/check_event_bus_integrity.py`
- `pytest -q`
