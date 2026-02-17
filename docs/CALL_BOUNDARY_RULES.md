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
4. 测试代码对核心域也遵循 facade 入口，不直连内部实现。

## 自动化检查
- `scripts/check_import_cycles.py`
- `scripts/check_call_boundaries.py`

触发失败条件：
- `CYCLE_COUNT > 0`
- `CALL_BOUNDARY_VIOLATION_COUNT > 0`
