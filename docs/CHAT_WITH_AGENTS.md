# 与 Agent 对话指南

## 当前通信模型（v2）
- 仅保留 `confess` 单播消息入口。
- 广播与 prayers 命令已移除。
- 消息状态通过 outbox 与 Angelia 事件队列观测。

## 1. 向单个 Agent 发送消息
```bash
./temple.sh confess genesis --title "任务指令" "请先检查 inbox 并完成本轮实现"
```

可选静默发送（不立即触发 wake 事件）：
```bash
./temple.sh confess genesis --title "记录" "仅记录，不立即执行" --silent
```

## 2. 查看消息送达状态（发送方）
```bash
./temple.sh inbox outbox --agent "High Overseer" --to genesis --limit 20
```

状态含义：
- `pending`: 已发送，未投递到执行上下文
- `delivered`: 已在某次 pulse 注入
- `handled`: pulse 处理完成并回执
- `failed`: 送达失败

## 3. 查看调度事件
```bash
./temple.sh angelia events --agent genesis --type inbox_event --state queued --limit 50
./temple.sh angelia agents
```

## 4. 常用排障路径
```bash
./temple.sh check genesis
./temple.sh angelia events --agent genesis --limit 100
./temple.sh inbox outbox --agent "High Overseer" --to genesis --limit 50
```

## 5. 推荐对话模板
```text
标题: 实现任务-A
内容: 目标是X，约束是Y，验收标准是Z。先给出计划，再执行并回传结果。
```

```text
标题: 修复缺陷-B
内容: 复现条件A，期望行为B，回归测试C。请先最小修复，再补测试。
```
