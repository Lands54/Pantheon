#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

RE_PREFIX = re.compile(r"^(re:|fw:|fwd:|回复:|答复:|转发:|回覆:|回復:)\s*", re.IGNORECASE)
RE_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
RE_CJK = re.compile(r"[\u4e00-\u9fff]")


@dataclass
class Msg:
    ts: float
    sender: str
    receiver: str
    title: str
    content: str
    event_id: str
    state: str
    attachments: int


def fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"


def norm_title(title: str) -> str:
    t = str(title or "").strip()
    while True:
        nt = RE_PREFIX.sub("", t).strip()
        if nt == t:
            break
        t = nt
    t = re.sub(r"\s+", " ", t)
    return t.lower()


def read_jsonl(path: Path) -> list[Msg]:
    out: list[Msg] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            out.append(
                Msg(
                    ts=float(row.get("created_at", 0) or 0),
                    sender=str(row.get("sender", "") or ""),
                    receiver=str(row.get("agent_id", "") or ""),
                    title=str(row.get("title", "") or ""),
                    content=str(row.get("content", "") or ""),
                    event_id=str(row.get("event_id", "") or ""),
                    state=str(row.get("state", "") or ""),
                    attachments=len(list(row.get("attachments", []) or [])),
                )
            )
    out.sort(key=lambda x: x.ts)
    return out


def build_threads(msgs: list[Msg], gap_sec: float = 6 * 3600) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for m in msgs:
        key = (m.sender, m.receiver, norm_title(m.title))
        bucket = by_key[key]
        if not bucket or m.ts - float(bucket[-1]["end_ts"]) > gap_sec:
            bucket.append(
                {
                    "id": "",
                    "sender": m.sender,
                    "receiver": m.receiver,
                    "title_norm": norm_title(m.title),
                    "titles": [m.title] if m.title else [],
                    "start_ts": m.ts,
                    "end_ts": m.ts,
                    "messages": [],
                }
            )
        cur = bucket[-1]
        cur["end_ts"] = m.ts
        if m.title and m.title not in cur["titles"]:
            cur["titles"].append(m.title)
        cur["messages"].append(
            {
                "ts": m.ts,
                "sender": m.sender,
                "receiver": m.receiver,
                "title": m.title,
                "event_id": m.event_id,
                "state": m.state,
                "attachments": m.attachments,
                "content": m.content,
            }
        )

    for groups in by_key.values():
        threads.extend(groups)

    threads.sort(key=lambda x: float(x["start_ts"]))
    for i, t in enumerate(threads, 1):
        t["id"] = f"thread_{i:04d}"
    return threads


def extract_topics(threads: list[dict[str, Any]], topk: int = 30) -> list[tuple[str, int]]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "you", "are", "our", "your", "can", "should",
        "have", "will", "please", "hello", "agent", "project", "ecosystem", "contract", "status", "role", "need",
        "系统", "代理", "我们", "你们", "需要", "请", "项目", "协作", "合同", "状态", "角色", "生态", "数据",
    }
    c = Counter()
    for t in threads:
        text = "\n".join(str(m.get("content", "")) for m in t.get("messages", []))
        for w in RE_WORD.findall(text):
            wl = w.lower()
            if wl in stop or len(wl) < 3:
                continue
            c[wl] += 1
        # 简单中文关键词：按常见词短语
        for kw in ["契约", "协商", "授粉", "捕食", "营养", "水循环", "种群", "边界", "时序", "接口", "集成", "投票", "议题"]:
            if kw in text:
                c[kw] += text.count(kw)
    return c.most_common(topk)


def summarize_thread(t: dict[str, Any]) -> dict[str, Any]:
    msgs = list(t.get("messages", []))
    first = msgs[0] if msgs else {}
    last = msgs[-1] if msgs else {}
    title = " / ".join(t.get("titles", [])[:3]) or t.get("title_norm", "(no title)")
    content_all = "\n".join(str(x.get("content", "")) for x in msgs)

    tags: list[str] = []
    rules = [
        ("contract", "契约/合同"),
        ("协议", "契约/合同"),
        ("vote", "投票"),
        ("投票", "投票"),
        ("predator", "捕食关系"),
        ("捕食", "捕食关系"),
        ("pollination", "授粉"),
        ("授粉", "授粉"),
        ("water", "水循环"),
        ("rain", "水循环"),
        ("nutrient", "营养循环"),
        ("decomposition", "分解循环"),
        ("integration", "系统集成"),
        ("接口", "系统集成"),
    ]
    low = content_all.lower()
    for k, tag in rules:
        if k in low or k in content_all:
            if tag not in tags:
                tags.append(tag)

    key_points = []
    if first:
        key_points.append(f"线程起点: {str(first.get('sender','-'))} -> {str(first.get('receiver','-'))}，主题 `{str(first.get('title','')).strip()}`")
    if last and last is not first:
        key_points.append(f"线程最新: {str(last.get('sender','-'))} -> {str(last.get('receiver','-'))}，状态 `{str(last.get('state','-'))}`")
    if "?" in content_all or "？" in content_all:
        key_points.append("包含明确问询/待确认项。")
    if "commit" in low or "提交" in content_all or "注册" in content_all:
        key_points.append("涉及契约注册/提交动作。")

    return {
        "thread_id": t.get("id"),
        "title": title,
        "sender": t.get("sender"),
        "receiver": t.get("receiver"),
        "start": fmt_ts(float(t.get("start_ts", 0) or 0)),
        "end": fmt_ts(float(t.get("end_ts", 0) or 0)),
        "message_count": len(msgs),
        "tags": tags,
        "key_points": key_points,
    }


def render_summary_md(project_id: str, threads: list[dict[str, Any]]) -> str:
    summaries = [summarize_thread(t) for t in threads]
    total = sum(int(s["message_count"]) for s in summaries)
    pair_counter = Counter(f"{s['sender']} -> {s['receiver']}" for s in summaries)
    tag_counter = Counter(tag for s in summaries for tag in s.get("tags", []))
    topics = extract_topics(threads)

    out: list[str] = []
    out.append(f"# {project_id} 私信翻译与总结报告")
    out.append("")
    out.append("## 全局概览")
    out.append("")
    out.append(f"- 线程数: **{len(summaries)}**")
    out.append(f"- 消息总数: **{total}**")
    if summaries:
        out.append(f"- 时间范围: **{summaries[0]['start']}** ~ **{summaries[-1]['end']}**")
    out.append("")

    out.append("## 高频通信对（Top 20）")
    out.append("")
    out.append("| 通信对 | 线程数 |")
    out.append("|---|---:|")
    for pair, cnt in pair_counter.most_common(20):
        out.append(f"| {pair} | {cnt} |")
    out.append("")

    out.append("## 主题标签统计")
    out.append("")
    out.append("| 标签 | 线程数 |")
    out.append("|---|---:|")
    for tag, cnt in tag_counter.most_common(20):
        out.append(f"| {tag} | {cnt} |")
    out.append("")

    out.append("## 关键词线索（启发式）")
    out.append("")
    for k, c in topics:
        out.append(f"- `{k}`: {c}")
    out.append("")

    out.append("## 线程级摘要")
    out.append("")
    for s in summaries:
        out.append(f"### {s['thread_id']} | {s['sender']} -> {s['receiver']}")
        out.append("")
        out.append(f"- 标题: {s['title']}")
        out.append(f"- 时间: {s['start']} ~ {s['end']}")
        out.append(f"- 消息数: {s['message_count']}")
        out.append(f"- 标签: {', '.join(s['tags']) if s['tags'] else '(无)'}")
        if s["key_points"]:
            out.append("- 要点:")
            for kp in s["key_points"]:
                out.append(f"  - {kp}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_translation_md(project_id: str, threads: list[dict[str, Any]]) -> str:
    out: list[str] = []
    out.append(f"# {project_id} 私信翻译稿（规则模式）")
    out.append("")
    out.append("说明：当前为规则模式落地，不调用外部翻译 API。中文原文保留；英文内容以“原文+中文摘要”形式呈现。")
    out.append("")

    for t in threads:
        s = summarize_thread(t)
        out.append(f"## {s['thread_id']} | {s['sender']} -> {s['receiver']}")
        out.append("")
        out.append(f"- 标题: {s['title']}")
        out.append(f"- 时间: {s['start']} ~ {s['end']}")
        out.append(f"- 中文摘要: {'；'.join(s['key_points']) if s['key_points'] else '无'}")
        out.append("")

        msgs = list(t.get("messages", []))
        # 每线程仅展开前2后1，避免文件爆炸
        pick = msgs[:2] + (msgs[-1:] if len(msgs) > 2 else [])
        for i, m in enumerate(pick, 1):
            content = str(m.get("content", ""))
            zh_hint = "中文原文" if RE_CJK.search(content) else "英文原文"
            out.append(f"### 样本消息 {i} ({zh_hint})")
            out.append("")
            out.append(f"- from/to: `{m.get('sender','-')} -> {m.get('receiver','-')}`")
            out.append(f"- time: `{fmt_ts(float(m.get('ts', 0) or 0))}`")
            out.append(f"- title: `{m.get('title','')}`")
            out.append("")
            out.append("```text")
            out.append(content)
            out.append("```")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Thread, translate-like render, and summarize private mails")
    ap.add_argument("--input", required=True, help="private mail JSONL")
    ap.add_argument("--project-id", default="animal_world_lab")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    in_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    msgs = read_jsonl(in_path)
    threads = build_threads(msgs)

    threads_json = out_dir / f"{args.project_id}_threads.json"
    translation_md = out_dir / f"{args.project_id}_translation.md"
    summary_md = out_dir / f"{args.project_id}_summary.md"

    threads_json.write_text(json.dumps(threads, ensure_ascii=False, indent=2), encoding="utf-8")
    translation_md.write_text(render_translation_md(args.project_id, threads), encoding="utf-8")
    summary_md.write_text(render_summary_md(args.project_id, threads), encoding="utf-8")

    print(f"threads={len(threads)} messages={len(msgs)}")
    print(f"threads_json={threads_json}")
    print(f"translation_md={translation_md}")
    print(f"summary_md={summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
