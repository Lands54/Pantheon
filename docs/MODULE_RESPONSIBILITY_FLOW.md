# 模块职责与信息流（收敛版）

## 1. 设计结论
- `Chaos`：原料组织层（只负责聚合资源，不定义策略）。
- `Metis`：策略层（消费 `Chaos` 输出，定义策略规格与执行包络）。
- Runtime 节点：只读 `__metis_envelope`，节点内无跨域拉取。

## 2. 模块职责与输入输出
| 模块 | 核心职责 | 主要输入 | 主要输出 | 输出主要被谁消费 |
|---|---|---|---|---|
| Angelia | 事件调度与 pulse 驱动 | EventBus/Iris 通知/Timer | pulse 执行触发（project_id, agent_id） | Runtime Engine |
| Chaos | 聚合策略原料 | Runtime state + Iris/Hermes/Mnemosyne/Config/StateWindow | `ResourceSnapshot` | Metis |
| Metis | 策略编排与包络构造 | `ResourceSnapshot` + StrategySpec + runtime state | `RuntimeEnvelope`（注入 `__metis_envelope`） | Runtime Nodes |
| Runtime Engine | 运行图与生命周期控制 | Angelia pulse + Metis envelope | 节点执行状态、next_step、finalize_control | Angelia Worker/调用方 |
| Janus | 上下文构建 sidecar | `RuntimeEnvelope` + directives/local memory | LLM messages | `llm_think` 节点 |
| Iris | mailbox 读写与收发回执 | Tools/interaction 事件 | mailbox intents、inbox/outbox 状态 | Chaos/Angelia |
| Mnemosyne | 记忆与意图持久化 | 运行意图/tool结果/事件语义 | 记忆策略结果、LLM可渲染文本 | Chaos/Janus |
| Hermes | 契约/协议/端口管理 | Tool 调用与系统操作 | 契约/协议状态、通知事件 | Chaos/Angelia |
| Config Registry | 配置单一真相源 | 配置模型与registry元数据 | schema/audit/校验结果 | API/CLI/前端/Runtime |
| Tools | 行为执行面 | LLM tool calls | domain side effects + tool result | Runtime dispatch |

## 3. 模块间主信息流（结构）
```mermaid
flowchart TD
    A["Angelia 调度"] -->|"触发 pulse"| E["Runtime Engine"]
    E -->|"请求原料聚合"| C["Chaos"]
    C -->|"ResourceSnapshot"| M["Metis"]
    M -->|"RuntimeEnvelope"| E
    E -->|"注入 __metis_envelope"| G["LangGraph Runtime Nodes"]

    G --> B1["build_context"]
    G --> B2["llm_think"]
    G --> B3["dispatch_tools"]
    G --> B4["decide_next"]

    B1 --> J["Janus"]
    J --> B2
    B2 --> B3
    B3 --> T["Tools"]
    T --> I["Iris"]
    T --> H["Hermes"]
    T --> N["Mnemosyne"]

    I --> C
    H --> C
    N --> C
    K["Config Registry"] --> C
```

## 4. 单次 pulse 时序
```mermaid
sequenceDiagram
    participant W as Angelia Worker
    participant E as Runtime Engine
    participant C as Chaos
    participant M as Metis
    participant G as Runtime Nodes
    participant J as Janus
    participant L as LLM
    participant T as Tools

    W->>E: 触发一次 pulse
    E->>C: 聚合原料
    C-->>E: ResourceSnapshot
    E->>M: 构建策略包络
    M-->>E: RuntimeEnvelope
    E->>G: invoke(state + __metis_envelope)

    G->>J: build_context(envelope)
    J-->>G: llm_messages
    G->>L: llm_think
    L-->>G: tool_calls

    loop 每个 tool_call
        G->>T: execute_tool
        T-->>G: result
    end

    G-->>E: next_step / finalize_control
    E-->>W: pulse 结束
```

## 5. 收敛约束
- Runtime 不再写入 `__chaos_envelope`。
- 策略规格来源固定为 `gods.metis.strategy_specs`。
- `Chaos` 不承载策略定义；`Metis` 不直接访问跨域基础设施（通过 Chaos 输出消费）。
- 跨模块调用必须通过 `facade`（禁止直接跨域 import `store/models/internal`）。
- CI/测试守卫：`/Users/qiuboyu/CodeLearning/Gods/tests/unit/test_architecture_facade_import_guard.py` 会阻止跨模块直连 `gods.<domain>.service`。
