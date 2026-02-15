# Gods Platform 架构图谱（Mermaid 多颗粒度）

> 兼容性结论：当前保持向后兼容。  
> - Project 级 `phase_strategy/phase_mode_enabled` 仍可用。  
> - Agent 级覆盖仅在显式设置 `agent.<id>.phase_strategy` 或 `agent.<id>.phase_enabled` 时生效。  
> - `api/server.py` 保留兼容导出，推荐新入口 `server.py -> api.app:app`。

## 1. 系统全景（L0）
```mermaid
flowchart TB
    U["User / Overseer"] --> CLI["CLI (temple.sh / cli.main)"]
    U --> FE["Frontend (optional)"]
    CLI --> API["FastAPI App (api.app)"]
    FE --> API
    API --> SVC["Service Layer (api.services)"]
    SVC --> G["Domain Core (gods/*)"]
    G --> FS["Project Filesystem (projects/{project_id})"]
    G --> OR["OpenRouter (LLM)"]
```

## 2. 分层边界（L1）
```mermaid
flowchart LR
    subgraph L0["Entry Layer"]
      SRV["server.py (root launcher)"]
      SH["server.sh"]
    end

    subgraph L1["API Layer"]
      APP["api.app (composition root)"]
      R1["api.routes.config"]
      R2["api.routes.projects"]
      R3["api.routes.hermes"]
      R4["api.routes.communication"]
      R5["api.routes.mnemosyne"]
    end

    subgraph L2["Service Layer"]
      CS["ConfigService"]
      PS["ProjectService"]
      SS["SimulationService"]
    end

    subgraph L3["Domain Layer (gods)"]
      AG["agents/*"]
      HM["hermes/*"]
      MN["mnemosyne/*"]
      TL["tools/*"]
      CFG["config.py"]
    end

    SRV --> APP
    SH --> SRV
    APP --> R1 & R2 & R3 & R4 & R5
    R1 --> CS
    R2 --> PS
    APP --> SS
    CS --> CFG
    PS --> HM & MN & CFG
    SS --> AG & CFG
    AG --> TL
```

## 3. API 到 Service 调用关系（L2）
```mermaid
flowchart TD
    RC["GET/POST /config"] --> CS["ConfigService"]
    RP["/projects/*"] --> PS["ProjectService"]
    APP["startup event"] --> SS["SimulationService"]

    CS --> C1["runtime_config read/write"]
    PS --> P1["project lifecycle"]
    PS --> P2["report build/load"]
    SS --> S1["pick_pulse_batch"]
    SS --> S2["pulse_agent_sync"]
```

## 4. 调度循环（L3 Runtime）
```mermaid
sequenceDiagram
    participant App as "api.app startup"
    participant Sim as "SimulationService"
    participant Sch as "api.scheduler"
    participant Agent as "GodAgent"

    App->>Sim: "pause_all_projects_on_startup()"
    App->>Sim: "create simulation_loop task"
    loop "every 1s"
      Sim->>Sch: "pick_pulse_batch(project, active_agents, batch_size)"
      Sch-->>Sim: "[(agent_id, reason)]"
      par "for each agent"
        Sim->>Sch: "pulse_agent_sync(project, agent, reason)"
        Sch->>Agent: "process(state)"
      end
    end
```

## 5. Agent 执行策略分流（L3 Agent）
```mermaid
flowchart TD
    Start["GodAgent.process()"] --> Pol["RuntimePolicy resolver"]
    Pol --> Mode["phase_mode_enabled?"]
    Mode -->|false| Legacy["Legacy loop (model<>tool)"]
    Mode -->|true| Strat["phase_strategy"]
    Strat -->|freeform| Legacy
    Strat -->|strict_triad/iterative_action| PR["AgentPhaseRuntime.run()"]
```

## 6. 配置覆盖优先级（Agent > Project）
```mermaid
flowchart TD
    Req["resolve_phase_strategy(project_id, agent_id)"] --> ASet["agent_settings[agent_id]"]
    ASet --> HasA{"agent override exists?"}
    HasA -->|yes| AVal["use agent phase_strategy"]
    HasA -->|no| PVal["use project phase_strategy"]
    AVal --> Norm["normalize invalid -> strict_triad"]
    PVal --> Norm
    Norm --> Out["final strategy"]
```

## 7. 严格阶段策略（strict_triad）
```mermaid
stateDiagram-v2
    [*] --> Reason
    Reason --> Act: "text plan only"
    Act --> Observe: "batch tool calls"
    Observe --> [*]: "finalize"
    Observe --> Reason: "no finalize (next pulse continue)"
```

## 8. 迭代策略（iterative_action）
```mermaid
flowchart TD
    R["Reason (once)"] --> A1["Act #1"]
    A1 --> O1["Observe #1"]
    O1 -->|finalize| End["finish"]
    O1 --> A2["Act #2"]
    A2 --> O2["Observe #2"]
    O2 -->|finalize| End
    O2 --> Cap{"interaction max reached?"}
    Cap -->|yes| Cont["continue (next pulse)"]
    Cap -->|no| A2
```

## 9. Hermes 协议总线（L3 Domain）
```mermaid
flowchart LR
    Caller["API/SDK/Agent Tool"] --> Reg["HermesRegistry"]
    Caller --> Exec["HermesExecutor"]
    Exec --> Lim["HermesLimiter"]
    Exec --> Rou["ProviderRouter"]
    Rou --> HT["HTTP provider"]
    Rou --> AT["agent_tool provider (default disabled)"]
    Exec --> Store["store.py (registry/invocations/jobs/contracts/ports)"]
```

## 10. Mnemosyne 档案流
```mermaid
sequenceDiagram
    participant Build as "ProjectService.build_report"
    participant Rep as "gods.project.reporting"
    participant Mn as "gods.mnemosyne.store"
    participant FS as "projects/{id}/mnemosyne/human"

    Build->>Rep: "build_project_report(project_id)"
    Rep->>Mn: "write_entry(vault='human', title='Project Report: {id}')"
    Mn->>FS: "append entries.jsonl + write entries/{entry_id}.md"
    Rep-->>Build: "report json/md paths + mnemosyne_entry_id"
```

## 11. 配置与安全（/config 脱敏）
```mermaid
flowchart TD
    Client["GET /config"] --> Route["api.routes.config"]
    Route --> Svc["ConfigService.get_config_payload"]
    Svc --> Mask["mask_api_key()"]
    Mask --> Resp["openrouter_api_key (redacted) + has_openrouter_api_key"]

    Client2["POST /config/save"] --> Route2["api.routes.config"]
    Route2 --> Save["ConfigService.save_config_payload"]
    Save --> Guard{"incoming key contains * ?"}
    Guard -->|yes| Skip["ignore masked key echo"]
    Guard -->|no| Persist["runtime_config.save()"]
```

## 12. 项目报告生成链路（Project 内报告）
```mermaid
flowchart LR
    Cmd["temple.sh project report <id>"] --> API["POST /projects/{id}/report/build"]
    API --> PS["ProjectService.build_report"]
    PS --> PR["gods.project.reporting.build_project_report"]
    PR --> Src1["protocols/registry.json"]
    PR --> Src2["protocols/invocations.jsonl"]
    PR --> Src3["protocols/contracts.json"]
    PR --> Src4["runtime/ports.json"]
    PR --> Src5["mnemosyne/*"]
    PR --> Out1["projects/{id}/reports/project_report.json"]
    PR --> Out2["projects/{id}/reports/project_report.md"]
    PR --> Out3["reports/project_{id}_latest.md (mirror)"]
```

## 13. CLI 命令分发结构
```mermaid
flowchart TD
    Main["cli.main"] --> Cfg["cli.commands.config"]
    Main --> Proj["cli.commands.project"]
    Main --> Prot["cli.commands.protocol"]
    Main --> Ag["cli.commands.agent"]
    Main --> Comm["cli.commands.communication"]
    Main --> Mn["cli.commands.mnemosyne"]
    Main --> Check["cli.commands.check"]
```

## 14. Project 目录数据平面
```mermaid
flowchart TB
    Root["projects/{project_id}/"] --> Agents["agents/{agent_id}/"]
    Root --> Buffers["buffers/*.jsonl"]
    Root --> Protocols["protocols/*"]
    Root --> Runtime["runtime/ports.json"]
    Root --> Reports["reports/project_report.*"]
    Root --> Mnemo["mnemosyne/{agent|human|system}/"]
    Root --> SQL["memory.sqlite"]

    Agents --> A1["agent.md"]
    Agents --> A2["memory.md"]
    Agents --> A3["memory_archive.md"]
    Agents --> A4["runtime_state.json"]
```

## 15. 兼容层关系图
```mermaid
flowchart LR
    Old["legacy import: api.server"] --> Compat["api/server.py (compat wrapper)"]
    Compat --> App["api.app:app"]
    Compat --> Sim["simulation_service.pause_all_projects_on_startup"]
    New["recommended launcher: server.py"] --> App
```

## 16. Agent 间交互方案（消息 + 协议双通道）
```mermaid
flowchart TD
    A["Agent A"] --> Msg["send_message / confess"]
    Msg --> Buf["projects/{id}/buffers/{agent}.jsonl"]
    Buf --> Sch["Scheduler inbox_event priority"]
    Sch --> B["Agent B pulse"]
    B --> Inbox["check_inbox tool"]
    Inbox --> Decision["Reason/Act/Observe decision"]

    A --> Prot["register_protocol / contract-register"]
    Prot --> Hermes["Hermes registry/contracts"]
    B --> Call["HermesClient invoke/route"]
    Call --> Hermes
    Hermes --> Result["sync result / async job"]
    Result --> B
```

## 17. Agent 工具调用执行链（Model<>Tool）
```mermaid
sequenceDiagram
    participant AG as "GodAgent"
    participant BR as "GodBrain"
    participant RT as "PhaseRuntime / LegacyLoop"
    participant TL as "Tool Layer (gods.tools)"
    participant FS as "Project Filesystem"

    AG->>RT: "build context + choose phase"
    RT->>BR: "think_with_tools(messages, tools)"
    BR-->>RT: "AIMessage(tool_calls)"
    loop "for each tool_call"
      RT->>TL: "execute_tool(name, args)"
      TL->>FS: "read/write/command/buffer/protocol"
      TL-->>RT: "observation string"
      RT->>AG: "append memory [[ACTION]]"
    end
    RT-->>AG: "next_step=finish|continue|escalated|abstained"
```

## 18. 契约机制总览（Hermes Contracts）
```mermaid
flowchart LR
    Submit["submitter agent"] --> Reg["/hermes/contracts/register"]
    Reg --> Store["protocols/contracts.json"]
    CommitA["agent A commit"] --> C1["/hermes/contracts/commit"]
    CommitB["agent B commit"] --> C1
    C1 --> Store
    Resolver["caller resolve"] --> Res["/hermes/contracts/resolved?title=&version="]
    Res --> Eff["effective obligations\n(agent-specific > default)"]
```

## 19. 契约生命周期（状态与动作）
```mermaid
stateDiagram-v2
    [*] --> Draft: "contract authoring"
    Draft --> Active: "register (status=active)"
    Active --> Active: "commit by agents"
    Active --> Active: "resolve obligations"
    Active --> Deprecated: "register new version / deprecate old"
    Deprecated --> Disabled: "manual disable (policy)"
    Disabled --> [*]
```

## 20. 契约解析规则（default + 专属职责）
```mermaid
flowchart TD
    In["contract row"] --> Comm["committers[]"]
    Comm --> Loop{"for each committer"}
    Loop --> HasSpec{"obligations[agent] exists?"}
    HasSpec -->|yes| UseSpec["use agent-specific obligations"]
    HasSpec -->|no| UseDef["use default_obligations"]
    UseSpec --> Out["resolved[agent]"]
    UseDef --> Out
```

## 21. 契约驱动调用路径（从承诺到执行）
```mermaid
flowchart TD
    Resolve["resolve contract"] --> Plan["agent gets obligations list"]
    Plan --> Impl["agent implements function / endpoint"]
    Impl --> Proto["register_protocol(name@version, provider)"]
    Proto --> Invoke["other agent invoke/route by protocol"]
    Invoke --> Audit["invocations.jsonl + job logs"]
    Audit --> Report["project report + mnemosyne archive"]
```

## 22. 动物世界专项：四代理协作拓扑（grass/sheep/tiger/ground）
```mermaid
flowchart LR
    GND["ground (集成/调度)"] --> GRS["grass (资源供给)"]
    GND --> SHP["sheep (摄食/繁衍)"]
    GND --> TGR["tiger (捕食压力)"]
    SHP --> GRS
    TGR --> SHP
    GRS --> GND
    SHP --> GND
    TGR --> GND
```

## 23. 动物世界专项：协商到实现时序
```mermaid
sequenceDiagram
    participant ground
    participant grass
    participant sheep
    participant tiger
    participant hermes

    ground->>grass: "send_message: propose ecosystem protocol"
    ground->>sheep: "send_message: request sheep obligations"
    ground->>tiger: "send_message: request tiger obligations"

    grass->>hermes: "register_protocol(grass.*)"
    sheep->>hermes: "register_protocol(sheep.*)"
    tiger->>hermes: "register_protocol(tiger.*)"

    ground->>hermes: "contract-register(eco.protocol)"
    grass->>hermes: "contract-commit"
    sheep->>hermes: "contract-commit"
    tiger->>hermes: "contract-commit"
    ground->>hermes: "contract-resolve"

    Note over ground,hermes: "resolved obligations -> implementation plan"
```

## 24. 动物世界专项：运行期调用环（协议主导）
```mermaid
flowchart TD
    Tick["pulse/inbox event"] --> GroundStep["ground step"]
    GroundStep --> CallGrass["route/invoke grass.update_biomass"]
    GroundStep --> CallSheep["route/invoke sheep.update_population"]
    GroundStep --> CallTiger["route/invoke tiger.update_predation"]

    CallGrass --> Hermes["Hermes"]
    CallSheep --> Hermes
    CallTiger --> Hermes

    Hermes --> R1["grass result"]
    Hermes --> R2["sheep result"]
    Hermes --> R3["tiger result"]

    R1 --> Integrate["ground integrate world state"]
    R2 --> Integrate
    R3 --> Integrate
    Integrate --> Persist["write_file / mnemosyne / invocation logs"]
```

## 25. 动物世界专项：消息通道与协议通道并存
```mermaid
flowchart LR
    subgraph Msg["消息通道 (buffers/*.jsonl)"]
      M1["send_message/confess"] --> M2["check_inbox"]
      M2 --> M3["协商文本 / 任务分配"]
    end

    subgraph Proto["协议通道 (Hermes)"]
      P1["register_protocol"] --> P2["invoke/route"]
      P2 --> P3["result + invocations.jsonl + jobs"]
    end

    M3 --> P1
    P3 --> M1
```

## 26. 动物世界专项：观测与复盘
```mermaid
flowchart TD
    Run["animal_world run"] --> Log1["agents/*/memory.md"]
    Run --> Log2["protocols/invocations.jsonl"]
    Run --> Log3["mnemosyne/human entries"]

    Log1 --> Report["project report build"]
    Log2 --> Report
    Log3 --> Report

    Report --> Out1["projects/{id}/reports/project_report.json"]
    Report --> Out2["projects/{id}/reports/project_report.md"]
    Report --> Out3["reports/project_{id}_latest.md"]
```
