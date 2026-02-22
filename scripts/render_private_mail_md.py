#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


def fmt_ts(v: Any) -> str:
    try:
        x = float(v)
    except Exception:
        return "-"
    return dt.datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M:%S")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def build_md(rows: list[dict[str, Any]], title: str) -> str:
    rows = sorted(rows, key=lambda x: float(x.get("created_at", 0) or 0))
    total = len(rows)
    first = fmt_ts(rows[0].get("created_at")) if rows else "-"
    last = fmt_ts(rows[-1].get("created_at")) if rows else "-"
    by_pair = Counter(f"{r.get('sender','-')} -> {r.get('agent_id','-')}" for r in rows)

    out: list[str] = []
    out.append(f"# {title}")
    out.append("")
    out.append("## 概览")
    out.append("")
    out.append(f"- 总私信数: **{total}**")
    out.append(f"- 起始时间: **{first}**")
    out.append(f"- 结束时间: **{last}**")
    out.append("")

    out.append("## 通信对计数（Top 50）")
    out.append("")
    out.append("| From -> To | Count |")
    out.append("|---|---:|")
    for pair, c in by_pair.most_common(50):
        out.append(f"| {pair} | {c} |")
    out.append("")

    out.append("## 全量私信")
    out.append("")
    for i, r in enumerate(rows, 1):
        sender = str(r.get("sender", "-"))
        receiver = str(r.get("agent_id", "-"))
        title_txt = str(r.get("title", "")).strip()
        state = str(r.get("state", "")).strip()
        eid = str(r.get("event_id", "")).strip()
        msg_type = str(r.get("msg_type", "")).strip()
        ts = fmt_ts(r.get("created_at"))
        content = str(r.get("content", ""))
        atts = r.get("attachments", [])
        if not isinstance(atts, list):
            atts = []

        out.append(f"### {i}. {sender} -> {receiver} | {title_txt or '(no title)'}")
        out.append("")
        out.append(f"- time: `{ts}`")
        out.append(f"- state: `{state}`")
        out.append(f"- event_id: `{eid}`")
        out.append(f"- msg_type: `{msg_type}`")
        out.append(f"- attachments_count: `{len(atts)}`")
        out.append("")
        out.append("```text")
        out.append(content)
        out.append("```")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Render agent private mails JSONL into human-readable Markdown")
    ap.add_argument("--input", required=True, help="Path to JSONL file")
    ap.add_argument("--output", required=True, help="Path to output Markdown file")
    ap.add_argument("--title", default="Agent Private Messages Export", help="Markdown title")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    rows = read_jsonl(in_path)
    md = build_md(rows, args.title)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"rendered={len(rows)} output={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
