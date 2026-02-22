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

TOPIC_RULES = [
    ("契约", "契约治理"), ("contract", "契约治理"), ("commit", "契约治理"), ("register", "契约治理"),
    ("pollination", "授粉网络"), ("授粉", "授粉网络"),
    ("predator", "捕食协同"), ("捕食", "捕食协同"), ("wolf", "捕食协同"), ("tiger", "捕食协同"),
    ("water", "水循环"), ("rain", "水循环"), ("river", "水循环"), ("wind", "水循环"),
    ("nutrient", "营养与分解"), ("decomposition", "营养与分解"), ("bacteria", "营养与分解"), ("fungi", "营养与分解"),
    ("state", "全局状态编排"), ("ecosystem", "全局状态编排"), ("ground", "全局状态编排"),
]

@dataclass
class Msg:
    ts: float
    sender: str
    receiver: str
    title: str
    content: str
    state: str
    event_id: str


def fmt_ts(v: float) -> str:
    return datetime.fromtimestamp(v).strftime("%Y-%m-%d %H:%M:%S")


def norm_title(title: str) -> str:
    t = str(title or "").strip()
    while True:
        nt = RE_PREFIX.sub("", t).strip()
        if nt == t:
            break
        t = nt
    return re.sub(r"\s+", " ", t).lower()


def read_msgs(path: Path) -> list[Msg]:
    rows: list[Msg] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                o = json.loads(s)
            except Exception:
                continue
            if not isinstance(o, dict):
                continue
            rows.append(Msg(
                ts=float(o.get("created_at", 0) or 0),
                sender=str(o.get("sender", "") or ""),
                receiver=str(o.get("agent_id", "") or ""),
                title=str(o.get("title", "") or ""),
                content=str(o.get("content", "") or ""),
                state=str(o.get("state", "") or ""),
                event_id=str(o.get("event_id", "") or ""),
            ))
    rows.sort(key=lambda x: x.ts)
    return rows


def classify_topic(text: str) -> str:
    t = text.lower()
    score = Counter()
    for k, topic in TOPIC_RULES:
        if k in t or k in text:
            score[topic] += 1
    if not score:
        return "其他协作"
    return score.most_common(1)[0][0]


def summarize_content(text: str, max_len: int = 180) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--project-id", default="animal_world_lab")
    args = ap.parse_args()

    msgs = read_msgs(Path(args.input))
    if not msgs:
        Path(args.output).write_text("# 空报告\n", encoding="utf-8")
        return 0

    total = len(msgs)
    pair_counter = Counter((m.sender, m.receiver) for m in msgs)
    sender_counter = Counter(m.sender for m in msgs)
    receiver_counter = Counter(m.receiver for m in msgs)
    state_counter = Counter(m.state for m in msgs)

    # threads by sender/receiver/title_norm within 6h
    threads = []
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for m in msgs:
        key = (m.sender, m.receiver, norm_title(m.title))
        arr = buckets[key]
        if not arr or (m.ts - float(arr[-1]["end_ts"])) > 6 * 3600:
            arr.append({"sender": m.sender, "receiver": m.receiver, "title": m.title, "title_norm": norm_title(m.title), "start_ts": m.ts, "end_ts": m.ts, "msgs": []})
        arr[-1]["end_ts"] = m.ts
        arr[-1]["msgs"].append(m)
    for arr in buckets.values():
        threads.extend(arr)
    threads.sort(key=lambda x: x["start_ts"])

    topic_counter = Counter()
    thread_rows = []
    for t in threads:
        all_text = (t["title"] + "\n" + "\n".join(m.content for m in t["msgs"]))
        topic = classify_topic(all_text)
        topic_counter[topic] += 1
        last = t["msgs"][-1]
        thread_rows.append({
            "topic": topic,
            "sender": t["sender"],
            "receiver": t["receiver"],
            "title": t["title"] or t["title_norm"],
            "start": t["start_ts"],
            "end": t["end_ts"],
            "count": len(t["msgs"]),
            "last_state": last.state,
            "last_excerpt": summarize_content(last.content),
        })

    # pick important threads
    important = sorted(thread_rows, key=lambda x: (x["count"], x["end"]), reverse=True)[:40]
    timeline = sorted(msgs, key=lambda x: x.ts)[-60:]

    lines = []
    lines.append(f"# {args.project_id} 私信精简报告")
    lines.append("")
    lines.append("## 一页结论")
    lines.append("")
    lines.append(f"- 总私信: **{total}**")
    lines.append(f"- 时间范围: **{fmt_ts(msgs[0].ts)} ~ {fmt_ts(msgs[-1].ts)}**")
    lines.append(f"- 活跃发送方 Top3: **{', '.join([f'{a}({b})' for a,b in sender_counter.most_common(3)])}**")
    lines.append(f"- 活跃接收方 Top3: **{', '.join([f'{a}({b})' for a,b in receiver_counter.most_common(3)])}**")
    lines.append(f"- 状态分布: **{', '.join([f'{k}={v}' for k,v in state_counter.items()])}**")
    lines.append("- 主议题：" + "、".join([f"{k}({v})" for k, v in topic_counter.most_common(6)]))
    lines.append("")

    lines.append("## 通信结构")
    lines.append("")
    lines.append("### 高频通信对 Top20")
    lines.append("")
    lines.append("| From | To | Count |")
    lines.append("|---|---|---:|")
    for (s, r), c in pair_counter.most_common(20):
        lines.append(f"| {s} | {r} | {c} |")
    lines.append("")

    lines.append("## 关键线程（压缩）")
    lines.append("")
    for i, t in enumerate(important, 1):
        lines.append(f"### {i}. [{t['topic']}] {t['sender']} -> {t['receiver']}")
        lines.append(f"- 标题: {t['title']}")
        lines.append(f"- 时间: {fmt_ts(t['start'])} ~ {fmt_ts(t['end'])}")
        lines.append(f"- 消息数: {t['count']} | 最新状态: {t['last_state']}")
        lines.append(f"- 最新摘要: {t['last_excerpt']}")
        lines.append("")

    lines.append("## 最近60条时间线（短摘要）")
    lines.append("")
    for m in timeline:
        lines.append(f"- `{fmt_ts(m.ts)}` {m.sender} -> {m.receiver} | {m.title or '(no title)'} | {summarize_content(m.content, 110)}")

    Path(args.output).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"written={args.output}")
    print(f"total={total} threads={len(threads)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
