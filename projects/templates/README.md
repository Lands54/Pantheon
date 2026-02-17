# Projects Templates

此目录用于存放可版本化的 Project 模板。
运行期项目数据位于 projects/<id>/，默认不纳入 git。

## 当前模板结构（vNext）

模板根：`projects/templates/default/`

关键目录：

1. `runtime/`
2. `runtime/locks/`
3. `mnemosyne/agent_profiles/`
4. `agents/`
5. `buffers/`

关键文件：

1. `runtime/events.jsonl`（统一事件总线）
2. `runtime/detach_jobs.jsonl`（detach 业务状态）
3. `mnemosyne/memory_policy.json`

说明：

1. 模板不再包含 `runtime/state_windows/`。
2. 模板不再包含任何 legacy 事件文件（如 `mail_events.jsonl`、`angelia_events.jsonl`、`inbox_events.jsonl`）。
