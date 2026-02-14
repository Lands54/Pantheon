# Gods: 分布式 Agent 开发系统架构

## 1. 核心愿景
构建一个高度自治、自主演化的分布式 Agent 集成平台。每一个 Agent 不仅是一个代码片段，而是一个拥有独立身份、独立环境（封闭文件夹）和核心职责的“数字生命实体”。

## 2. 目录结构规范
系统将遵循严格的物理隔离模式：

```text
Gods/
├── platform/               # 平台核心引擎
│   ├── bus/                # 消息传递与路由中心
│   ├── parser/             # Agent 语义与调用解析器
│   └── registry/           # Agent 注册与状态维护
├── agents/                 # Agent 物理隔离区
│   └── {agent_id}/         # 每个 Agent 的专属领地
│       ├── agent.md        # Agent 的灵魂：定义核心职责、身份与知识
│       ├── .agent/         # Agent 的私有元数据与记忆
│       ├── workspace/      # Agent 自由操作的源码与程序空间
│       └── logs/           # 行为审计日志
└── shared/                 # 全局协议与标准库
```

## 3. Agent 规格说明 (agent.md)
每个 Agent 必须包含一个 `agent.md`，其结构定义如下：
- **Identity**: Agent 名称与 ID。
- **Core Responsibility**: (核心职责) **最重要**的部分，定义了 Agent 存在的唯一理由。
- **Capability**: 描述 Agent 能够调用的工具和具备的技能。
- **State**: 当前任务状态。

## 4. 通信协议 (Call & Message)
Agent 之间不直接调用，而是通过平台解析指令：
- **Private Call**: `[[send(to="agent_b", msg="...")]]`
- **Group Call**: `[[broadcast(group="dev_team", msg="...")]]`
- **Tool Call**: `[[exec(runtime="python", code="...")]]` - 允许 Agent 在自身 `workspace` 内编写并运行代码。

## 5. 平台演进规划
- **Phase 1**: 环境基础与 Agent 注册机制实现。
- **Phase 2**: 基于文件监听的消息总线 (Message Bus) 建立。
- **Phase 3**: 语义解析引擎，支持 Agent 理解并触发 `call`。
- **Phase 4**: 分布式部署支持。
