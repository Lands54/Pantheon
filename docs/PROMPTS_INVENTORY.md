# Gods Platform 硬编码提示词清单

本文档列出当前代码中直接硬编码的系统提示/上下文模板，便于统一治理。

## 1) Agent 主流程上下文

文件：`gods/agents/base.py`

- `simulation_directives` 中硬编码：
  - `# SOCIAL PROTOCOL`
  - `You are an AVATAR in a shared world.`
  - `PRIORITIZE private messages (Inbox)...`
  - `ESCALATE to the Public Synod...`
- `build_context()` 中硬编码结构块：
  - `# IDENTITY`
  - `# SACRED INBOX (Incoming Private Revelations)`
  - `# YOUR CHRONICLES (memory.md)`
  - `# TERRITORY`
  - `# GLOBAL RECORD & SYNOD HISTORY`
  - `# TASK (Current Universal Intent)`
  - `# AVAILABLE TOOLS`
  - `# PROTOCOL`（含 1~6 条流程规则）

## 2) 摘要器提示词

文件：`gods/workflow.py`

- `summarize_conversation()` 中硬编码 prompt：
  - `Summarize the following theological history for project ...`

## 3) 通信路由注入上下文

文件：`api/routes/communication.py`

- 广播消息前缀：
  - `SACRED DECREE: {req.message}`
- confess 来源固定：
  - `"from": "High Overseer"`

## 4) 调度器脉冲上下文

文件：`api/scheduler.py`

- 脉冲 context 硬编码：
  - `PULSE_EVENT: {reason}`
  - `Autonomous pulse reason={reason}`

## 5) 动物世界自治实验脚本

文件：`scripts/run_animal_world_emergent.py`

- `MISSION` 固定文本
- `_agent_directive()` 中完整自治原则为硬编码（含边界、协商、record_protocol、收件箱规则、产出约束）
- `run_emergent_rounds()` 中轮次上下文：
  - `SACRED DECREE ROUND {i}: ...`
  - `EXISTENCE_PULSE ROUND {i}: ...`

## 6) 用户可见“警告/限制”提示文案（非系统思维提示，但会影响行为）

文件：`gods/tools/communication.py`, `gods/tools/execution.py`, `gods/tools/filesystem.py`

- Inbox guard 警告：
  - `Inbox Empty Warning: ...`
  - `Divine Warning: inbox still empty...`
- 执行限制：
  - `Divine Restriction: ...`

## 7) 当前问题结论（与提示词相关）

1. 关键提示词分散在多个模块，缺少统一版本管理。  
2. Agent 流程提示（`base.py`）与实验脚本提示（`run_animal_world_emergent.py`）存在叠加和冲突风险。  
3. 摘要器、调度器、通信路由都在各自注入语义，整体行为难以推演。

## 8) 建议的下一步（统一提取方向）

1. 新建 `gods/prompts/` 目录，按用途拆分：
   - `agent_system.md`
   - `agent_protocol.md`
   - `summarizer.txt`
   - `scheduler_event.txt`
2. 由 `PromptRegistry` 统一加载并按项目覆盖（支持 `projects/{id}/prompts/`）。
3. 在 `config.json` 增加 prompt 版本号与开关，便于 A/B 行为对比。
