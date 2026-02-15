# Hermes Agent 使用手册（Project 级协议系统）

本手册面向 Agent，说明如何在 Gods Platform 中正确使用 Hermes 完成跨代理协作与代码级协议调用。

## 1. 你要记住的核心原则

1. 所有协议都是 **Project 级隔离**。
2. 跨代理能力调用优先走 Hermes，不要假设对方文件结构。
3. 当前默认策略下，`agent_tool` provider 禁用；优先使用 `http` provider。
4. 协议名必须是 `namespace.action`，Hermes 内部按名称维护单一当前定义（无协议版本号）。

## 2. Hermes 提供的能力

1. 协议注册：把一个能力声明为可调用协议。
2. 协议调用：`sync` 或 `async` 调用协议（通过代码/SDK）。
3. 路由调用：按 `target_agent + function_id` 直接路由（通过代码/SDK）。
4. 契约管理：提交契约 JSON、承诺加入、解析每个承诺人的职责。
5. 运行可观测：每次注册/调用都会进入 Hermes 日志和事件流。
6. 端口租约：启动本机 HTTP 服务前先向 Hermes 申请端口，避免冲突。

## 3. 常用工具（Agent 内，治理面）

1. `register_contract`
- 作用：提交结构化契约 JSON。

2. `commit_contract`
- 作用：当前 Agent 承诺加入契约版本。

3. `list_contracts`（查看缺签与激活状态）
- 作用：解析契约后每个承诺人应实现的职责。

4. `list_contracts`
- 作用：检索契约摘要（title/version/description/status），默认只显示 active。

5. `disable_contract`
- 作用：退出当前 Agent 对契约的承诺；当承诺人清空后契约自动 disabled。

6. `reserve_port`
- 作用：申请本机端口租约（Project 级）。

7. `release_port`
- 作用：释放端口租约。

8. `list_port_leases`
- 作用：查看当前项目已租约端口。

说明：
- 协议“执行调用”不再通过 Agent tool，统一由业务代码通过 `HermesClient` 完成。
- `register_protocol/list_protocols/record_protocol` 为兼容层，默认不在 Agent 工具集中。

## 4. 标准工作流

### 4.1 发布协议

1. 先设计契约与条款（每个条款包含可执行 provider/schema/runtime）。
2. 使用 `register_contract` 提交契约。
3. 相关承诺人执行 `commit_contract`，系统自动在全员提交后生效。

### 4.2 调用协议

1. 先 `list_contracts` 确认 `missing_committers=[]` 且 `is_fully_committed=true`。
2. 在业务代码里使用 `HermesClient.invoke(mode="sync")` 或 `route(...)` 获取结果。
3. 长任务用 `mode="async"`，然后 `HermesClient.wait_job` 等待完成。

### 4.3 路由调用（神间语义）

1. 协议注册时仅需提供：
- `owner_agent`: 该函数归属神
- `function_id` 由 Hermes 自动生成：`owner_agent + "." + name尾段`（无需手填）

2. 调用时使用：
- `HermesClient.route(target_agent="fire_god", function_id="check_fire_speed", payload={...})`

Hermes 会自动匹配该神的该函数的当前可用协议并执行。

## 5. 契约 JSON（推荐结构）

```json
{
  "version": "1.0.0",
  "title": "生态系统协作契约",
  "description": "定义跨代理协作目标、边界、成功标准与可执行条款。",
  "submitter": "ground",
  "committers": ["grass"],
  "status": "active",
  "default_obligations": [
    {
      "id": "sync_state",
      "summary": "同步当前生态状态",
      "io": {
        "request_schema": {"type": "object"},
        "response_schema": {"type": "object"}
      },
      "runtime": {"mode": "sync", "timeout_sec": 10}
    }
  ],
  "obligations": {
    "grass": [
      {
        "id": "check_fire_speed",
        "summary": "检查火势速度",
        "io": {
          "request_schema": {"type": "object", "required": ["v"]},
          "response_schema": {"type": "object"}
        },
        "runtime": {"mode": "sync", "timeout_sec": 10}
      }
    ]
  }
}
```

### 解析规则

1. `obligations[agent]` 有定义时，优先使用专属职责。
2. 没有专属定义时，自动继承 `default_obligations`。
3. 新承诺人加入（`commit_contract`）且未专属定义，默认承担 `default_obligations`。

### 状态规则（active / disabled）

1. `commit_contract` 仅允许在 `active` 契约上执行。
2. `disabled` 契约不会接受新的 commit；请通过 `contract-list --include-disabled` 检查状态与缺签信息。
3. `disable_contract` 的语义是“退出承诺”；当承诺人变为 0 时契约自动 disabled。

## 6. Provider 策略

### 6.1 推荐：`http`

- 适合业务代码互调。
- 当前只允许本机地址：`localhost` / `127.0.0.1` / `::1`。

### 6.2 `agent_tool`

- 默认禁用（安全策略）。
- 仅在项目显式开启 `hermes_allow_agent_tool_provider=true` 时可用。

## 7.5 端口管理流程（强烈推荐）

1. 服务启动前：
- `reserve_port(owner_id="grass_api")` 获取可用端口。

2. 用租约端口启动 HTTP 服务并注册协议 URL。

3. 服务停止时：
- `release_port(owner_id="grass_api", port=...)` 释放租约。

## 7. 常见错误与修复

1. `HERMES_PROTOCOL_NOT_FOUND`
- 原因：协议名错误或未注册。
- 处理：先 `list_contracts` 确认 commit 状态与缺签名单，再重试。

2. `HERMES_SCHEMA_INVALID`
- 原因：payload 或返回结果不符合 schema。
- 处理：修正请求字段或 provider 输出结构。

3. `HERMES_AGENT_TOOL_DISABLED`
- 原因：尝试使用 `agent_tool`，但项目策略未允许。
- 处理：改用 `http` provider，或由人类开启配置。

4. `HERMES_RATE_LIMITED` / `HERMES_BUSY`
- 原因：调用过于密集或并发超限。
- 处理：指数退避重试，降低并发。

## 8. 最佳实践

1. 先契约后编码：先 `register_contract`，再拆分职责开发。
2. 协议最小化：一个协议只做一件清晰的事。
3. 强 schema：请求和响应都写严格字段，减少歧义。
4. 可观测优先：关键调用统一走 Hermes，便于追踪。
5. 版本演进：新能力用新版本，不直接破坏旧版本。

## 8.5 Project 报告（复盘入口）

实验复盘能力已收敛到 Project 层，不再使用独立 experiment 子系统。

1. 生成报告：
- `./temple.sh project report <project_id>`

2. 查看报告 JSON：
- `./temple.sh project report-show <project_id>`

3. 输出位置：
- `projects/{project_id}/reports/project_report.json`
- `projects/{project_id}/reports/project_report.md`
- `reports/project_{project_id}_latest.md`（镜像）

4. 报告会自动落档到 Mnemosyne human vault，便于人类审阅与追踪。

## 8.6 兼容层说明

1. `legacy social api` 处于 deprecated 兼容层，默认关闭。
2. `simulation.parallel` 保留为兼容字段，当前实现中视为 no-op。

## 9. 一句话模板（给 Agent）

> 跨代理协作时，先查协议，再按 schema 调用 Hermes；需要按神和函数调用时使用 route；职责分配先提交 contract，再 commit，再 resolve 后执行。

## 10. 代码 SDK（HermesClient）

项目提供 Python SDK：`gods.hermes.client.HermesClient`，用于业务代码直接调用 Hermes。

示例：

```python
from gods.hermes.client import HermesClient

client = HermesClient(base_url="http://localhost:8000", timeout_sec=20)

# 路由调用：Hermes(火神, check_fire_speed, payload)
ret = client.route(
    project_id="animal_world",
    caller_id="ground_service",
    target_agent="fire_god",
    function_id="check_fire_speed",
    payload={"wind": 3.2},
    mode="sync",
)
print(ret)

# 端口租约
lease = client.reserve_port("animal_world", "grass_api")
port = lease["lease"]["port"]

# 异步任务等待
job = client.invoke("animal_world", "ground", "grass.scan", {"path": "."}, mode="async")
final = client.wait_job("animal_world", job["job_id"], timeout_sec=60)
print(final)
```
