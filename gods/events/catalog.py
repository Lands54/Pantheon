"""Event catalog with semantic description and LLM-feed metadata."""
from __future__ import annotations

from typing import Any


_CATALOG: dict[str, dict[str, Any]] = {
    # Interaction events (agent/human visible)
    "interaction.message.sent": {
        "domain": "interaction",
        "title": "发送消息请求",
        "description": "交互层消息请求入口；在 interaction 内同步转化为 mailbox 领域事件。",
        "feeds_llm": False,
        "llm_note": "路由层事件，不直接注入 LLM。",
    },
    "interaction.message.read": {
        "domain": "interaction",
        "title": "消息已读回执",
        "description": "更新消息处理状态（已读/已处理），用于状态闭环。",
        "feeds_llm": False,
        "llm_note": "仅状态回执，不注入 LLM。",
    },
    "interaction.hermes.notice": {
        "domain": "interaction",
        "title": "Hermes 通知分发",
        "description": "将 Hermes 事件转成可投递消息并分发给目标 Agent（同步路由层）。",
        "feeds_llm": False,
        "llm_note": "路由层事件，不直接注入 LLM。",
    },
    "interaction.detach.notice": {
        "domain": "interaction",
        "title": "Detach 生命周期通知",
        "description": "将 detach 运行态变化通知到 Agent（同步路由层）。",
        "feeds_llm": False,
        "llm_note": "路由层事件，不直接注入 LLM。",
    },
    "interaction.agent.trigger": {
        "domain": "interaction",
        "title": "Agent 触发执行",
        "description": "历史触发事件（已收敛，禁止模块常规产出）。",
        "feeds_llm": False,
        "llm_note": "保留兼容读取；新触发请使用 angelia.timer/manual/system。",
    },
    # Iris mailbox
    "mail_event": {
        "domain": "iris",
        "title": "邮件可处理事件",
        "description": "邮箱中存在待处理消息，驱动 Agent 消费 inbox。",
        "feeds_llm": True,
        "llm_note": "消息会进入上下文构建并影响 LLM 输入。",
    },
    "mail_deliver_event": {
        "domain": "iris",
        "title": "邮件投递事件",
        "description": "邮件投递过程中的内部语义事件。",
        "feeds_llm": False,
        "llm_note": "内部状态语义，不直接喂给 LLM。",
    },
    "mail_ack_event": {
        "domain": "iris",
        "title": "邮件确认事件",
        "description": "邮件回执/确认的内部语义事件。",
        "feeds_llm": False,
        "llm_note": "内部状态语义，不直接喂给 LLM。",
    },
    # Angelia scheduler
    "timer": {
        "domain": "angelia",
        "title": "定时触发",
        "description": "定时调度触发一次 Agent 运行。",
        "feeds_llm": True,
        "llm_note": "通常触发一次 Agent 执行与 LLM 推理。",
    },
    "manual": {
        "domain": "angelia",
        "title": "手动触发",
        "description": "人工或系统手动触发 Agent 执行。",
        "feeds_llm": True,
        "llm_note": "通常触发一次 Agent 执行与 LLM 推理。",
    },
    "system": {
        "domain": "angelia",
        "title": "系统触发",
        "description": "系统内部触发的执行事件。",
        "feeds_llm": True,
        "llm_note": "通常触发一次 Agent 执行与 LLM 推理。",
    },
    # Hermes
    "hermes_protocol_invoked_event": {
        "domain": "hermes",
        "title": "协议调用记录",
        "description": "记录协议被调用的业务事件。",
        "feeds_llm": False,
        "llm_note": "模块内业务记录，不直接喂给 LLM。",
    },
    "hermes_job_updated_event": {
        "domain": "hermes",
        "title": "Hermes 任务更新",
        "description": "记录 Hermes 任务状态变化。",
        "feeds_llm": False,
        "llm_note": "模块内业务记录，不直接喂给 LLM。",
    },
    "hermes_contract_registered_event": {
        "domain": "hermes",
        "title": "契约注册",
        "description": "记录契约注册行为。",
        "feeds_llm": False,
        "llm_note": "若需通知 Agent，会再转为 interaction.hermes.notice。",
    },
    "hermes_contract_committed_event": {
        "domain": "hermes",
        "title": "契约提交",
        "description": "记录契约提交/阶段性达成。",
        "feeds_llm": False,
        "llm_note": "若需通知 Agent，会再转为 interaction.hermes.notice。",
    },
    "hermes_contract_disabled_event": {
        "domain": "hermes",
        "title": "契约停用",
        "description": "记录契约停用行为。",
        "feeds_llm": False,
        "llm_note": "若需通知 Agent，会再转为 interaction.hermes.notice。",
    },
    # Runtime detach
    "detach_submitted_event": {
        "domain": "runtime",
        "title": "Detach 提交",
        "description": "提交一个 detach 任务。",
        "feeds_llm": False,
        "llm_note": "控制面事件；如需通知 Agent，会转 interaction.detach.notice。",
    },
    "detach_started_event": {
        "domain": "runtime",
        "title": "Detach 启动",
        "description": "detach 任务已启动。",
        "feeds_llm": False,
        "llm_note": "控制面事件；如需通知 Agent，会转 interaction.detach.notice。",
    },
    "detach_stopping_event": {
        "domain": "runtime",
        "title": "Detach 停止中",
        "description": "detach 任务进入停止流程。",
        "feeds_llm": False,
        "llm_note": "控制面事件；如需通知 Agent，会转 interaction.detach.notice。",
    },
    "detach_stopped_event": {
        "domain": "runtime",
        "title": "Detach 已停止",
        "description": "detach 任务已停止。",
        "feeds_llm": False,
        "llm_note": "控制面事件；如需通知 Agent，会转 interaction.detach.notice。",
    },
    "detach_failed_event": {
        "domain": "runtime",
        "title": "Detach 失败",
        "description": "detach 任务执行失败。",
        "feeds_llm": False,
        "llm_note": "控制面事件；如需通知 Agent，会转 interaction.detach.notice。",
    },
    "detach_reconciled_event": {
        "domain": "runtime",
        "title": "Detach 对账完成",
        "description": "detach 任务状态完成一次 reconcile。",
        "feeds_llm": False,
        "llm_note": "控制面事件；如需通知 Agent，会转 interaction.detach.notice。",
    },
    "detach_lost_event": {
        "domain": "runtime",
        "title": "Detach 丢失",
        "description": "detach 任务被判定丢失/不可追踪。",
        "feeds_llm": False,
        "llm_note": "控制面事件；如需通知 Agent，会转 interaction.detach.notice。",
    },
}


def event_catalog() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for et, meta in sorted(_CATALOG.items(), key=lambda x: (str(x[1].get("domain", "")), x[0])):
        out.append({"event_type": et, **meta})
    return out


def event_meta(event_type: str) -> dict[str, Any] | None:
    row = _CATALOG.get(str(event_type or "").strip())
    if not row:
        return None
    return {"event_type": str(event_type), **row}
