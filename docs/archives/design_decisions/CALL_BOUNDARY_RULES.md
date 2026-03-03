# 模块调用边界规则

## 目标
统一调用链：`api/routes -> api/services -> gods.<domain>.facade`。

## 规则
1. `api/routes/*` 只能依赖：
   - `api.services.*`
   - `api.models`
   - FastAPI / Pydantic / 标准库
2. `api/services/*` 调用领域能力时，只能走：
   - `gods.<domain>.facade`
   - 或 `gods.<domain>` 顶层公开导出
3. `gods` 核心域（`angelia|iris|hermes|mnemosyne|janus|runtime`）跨域调用，必须走对方 `facade`。
4. 测试代码对核心域默认也遵循 facade 入口，不直连内部实现。
5. 白盒例外：仅 `tests/whitebox/<domain>/**` 允许访问该 `<domain>` 的内部实现，且必须在文件头声明 `@whitebox-reason:`；白盒测试依然禁止跨域内部导入（跨域只能走 facade）。

## 事件职责边界（vNext）
1. `gods.events` 是统一事件总线（`events.jsonl`），仅承载传输态（`queued/picked/processing/done/failed/dead`）。
2. `gods.iris` 负责 Mail 业务状态机（deliver/handled/receipt）并通过 facade 对外提供 mailbox 语义。
3. `gods.angelia` 负责调度执行与 worker 生命周期；执行必须经 `EventHandler` registry。
4. `mailbox notify/wait` 仅是唤醒机制，不可作为事件真实状态来源。

## API 边界（Breaking）
1. 新统一入口：`/events/*`。
2. Agent 交互消息只允许 `domain=interaction`（`interaction.message.* / interaction.hermes.notice / interaction.detach.notice`）。
3. 旧 ` /angelia/events* `、`/projects/{project_id}/detach/*` 与 `/confess` 已移除。

## 强禁规则（vNext）
1. `gods/hermes/*` 禁止直连 `gods.iris.facade.enqueue_message`。
2. `gods/tools/comm_human.py` 禁止直连 `gods.iris.*`，必须提交 interaction 事件。

## 自动化检查
- `scripts/check_import_cycles.py`
- `scripts/check_call_boundaries.py`
- `scripts/check_no_legacy_paths.py`（禁止 legacy phase/runtime 路径）

触发失败条件：
- `CYCLE_COUNT > 0`
- `CALL_BOUNDARY_VIOLATION_COUNT > 0`
- `LEGACY_PATH_GUARD != PASS`

## Runtime 收口规则
1. 禁止新增或引用 `gods.agents.phase_runtime`。
2. 禁止使用旧策略名 `strict_triad|iterative_action`。
3. `phase_strategy` 仅允许 `react_graph|freeform`。
