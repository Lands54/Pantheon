# EVENT HANDLER DEVELOPER GUIDE

## 1. 目标
通过 `EventHandler` 五阶段统一事件执行，禁止 worker 中按 `if event_type` 写业务分支。

## 2. 接口
在 `gods/events/handler.py` 实现：
- `on_pick(record)`
- `on_process(record)`
- `on_success(record, result)`
- `on_fail(record, err)`
- `on_dead(record, err)`

## 3. 注册
- 使用 `gods/events/registry.py`：`register_handler(event_type, handler)`
- worker 通过 `get_handler(event_type)` 分发

## 4. 约束
1. handler 不得直接写 `events.jsonl`。
2. handler 失败只抛异常，由 worker/store 统一推进重试或 dead。
3. handler 内跨域调用只允许走 `gods.<domain>.facade`。

## 5. 最小示例
```python
from gods import events as events_bus

class MyHandler(events_bus.EventHandler):
    def on_process(self, record):
        payload = record.payload or {}
        return {"ok": True, "echo": payload}

events_bus.register_handler("my_event", MyHandler())
```

## 6. 测试建议
- 生命周期顺序测试（pick -> process -> success/fail/dead）
- 非法状态迁移拒绝
- 幂等重放与 dedupe
