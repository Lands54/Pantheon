# 模块边界审计（本轮）

## 1. 职责冲突清单
- `api/routes` 与领域实现耦合：历史上 routes 直接依赖 `gods.*` 内部实现，已收口至 service。
- 调度能力分散：`angelia` 与 `angelia/pulse` 共存，已通过 `gods.angelia.facade` 统一对外入口。

## 2. 重复/冗余清单
- 项目解析 `_pick_project` 在多个 route 重复实现：已下沉为 `api/services/common/project_context.py`。
- 多个 route 重复做业务编排：已迁移至 `agent/angelia/hermes/mnemosyne/tool_gateway` service。

## 3. 调用复杂度热点
- 旧 `api/routes/hermes.py` 扇出高（协议/契约/端口/事件流混合）：已由 `api/services/hermes_service.py` 集中编排。
- 旧 `api/routes/tool_gateway.py` 直接调用 tools：已改为 `api/services/tool_gateway_service.py`。

## 4. 不可调用/可疑孤儿能力
- `gods/angelia/pulse/queue.py`：当前非运行主链必需。
  - 状态：保留。
  - 标记：源码包含 `@orphaned` 注释。
  - 原因：作为诊断/兼容能力仍被测试覆盖。
  - 后续：在下一轮评估是否删除或彻底并入 Angelia 事件主链。

## 5. 本轮合规结果目标
- API 路由不再直接依赖 `gods.*`。
- service 对领域依赖统一为 facade。
- 新增边界检查脚本与单测，阻断回退。
