# AGENT RUNTIME LANGGRAPH

## 1. 目标
统一 Agent 运行时执行器，替换旧 phase runtime 与 legacy freeform 循环。

## 2. 入口与结构
1. 入口：`gods/agents/runtime/engine.py:run_agent_runtime`
2. 状态定义：`gods/agents/runtime/models.py:RuntimeState`
3. 节点实现：`gods/agents/runtime/nodes.py`
4. 策略注册：`gods/agents/runtime/registry.py`
5. 策略构建器：
   - `gods/agents/runtime/strategies/react_graph.py`
   - `gods/agents/runtime/strategies/freeform.py`

## 3. 执行图
通用节点链路：
`build_context -> llm_think -> dispatch_tools -> decide_next`

路由：
1. `route=again` 回到 `build_context`
2. `route=done` 结束

## 4. 策略说明
1. `react_graph`
   - 默认策略
   - 面向标准 ReAct 循环
2. `freeform`
   - 同样运行在 LangGraph 上
   - 保留自由交互风格（低约束）

## 5. 配置
1. 项目级：`projects.<pid>.phase_strategy`
2. Agent 覆盖：`projects.<pid>.agent_settings.<aid>.phase_strategy`
3. 允许值仅：`react_graph|freeform`

## 6. 扩展规范
新增策略时：
1. 在 `strategies/` 新增 graph builder
2. 在 `registry.py` 注册策略名
3. 补充单元/集成测试覆盖
4. 不得修改公共节点职责以适配单一策略
