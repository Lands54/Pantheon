# 测试边界策略

## 目标
在保证架构收口不回退的前提下，允许必要的白盒验证。

## 分层
1. 黑盒测试（默认）
   - 路径：`tests/**`（不含 `tests/whitebox/**`）
   - 规则：核心域只允许通过 `gods.<domain>.facade` 导入。
2. 白盒测试（受控例外）
   - 路径：`tests/whitebox/<domain>/**`
   - 规则：
     - 允许导入同域内部实现（`gods.<domain>.*`）
     - 禁止跨域内部导入（如在 `runtime` 白盒里导入 `gods.janus.strategies.*`）
     - 文件头前 40 行必须包含 `@whitebox-reason:`，说明白盒必要性

## 自动化
- `scripts/check_call_boundaries.py` 会校验上述规则。
- 违反即 `CALL_BOUNDARY_VIOLATION_COUNT > 0`，CI 失败。
