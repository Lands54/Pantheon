"""Mnemosyne chronicle compaction (token-triggered, strategy-switchable)."""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from gods.config import runtime_config
from gods.paths import mnemosyne_dir


def _mn_root(project_id: str) -> Path:
    p = mnemosyne_dir(project_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def chronicle_path(project_id: str, agent_id: str) -> Path:
    p = _mn_root(project_id) / "chronicles" / f"{agent_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def archive_path(project_id: str, agent_id: str) -> Path:
    p = _mn_root(project_id) / "chronicles" / f"{agent_id}_archive.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def token_io_path(project_id: str, agent_id: str) -> Path:
    p = _mn_root(project_id) / "token_io" / f"{agent_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _tok_len(text: str) -> int:
    return max(1, len(str(text or "")) // 4)


def _project(project_id: str):
    return runtime_config.projects.get(project_id)


def compact_trigger_tokens(project_id: str) -> int:
    proj = _project(project_id)
    v = int(getattr(proj, "memory_compact_trigger_tokens", 12000) if proj else 12000)
    return max(2000, min(v, 256000))


def compact_strategy(project_id: str) -> str:
    proj = _project(project_id)
    raw = str(getattr(proj, "memory_compact_strategy", "semantic_llm") if proj else "semantic_llm").strip().lower()
    if raw not in {"semantic_llm", "rule_based"}:
        return "semantic_llm"
    return raw


def _resolve_compaction_model(project_id: str, agent_id: str) -> str:
    proj = _project(project_id)
    aid = str(agent_id or "").strip()
    if proj and aid and aid in getattr(proj, "agent_settings", {}):
        try:
            m = str(proj.agent_settings[aid].model or "").strip()
            if m:
                return m
        except Exception:
            pass
    return "stepfun/step-3.5-flash:free"


def note_llm_token_io(
    project_id: str,
    agent_id: str,
    *,
    mode: str,
    estimated_context_tokens: int = 0,
    prompt_tokens: int = 0,
    total_tokens: int = 0,
):
    row = {
        "timestamp": time.time(),
        "project_id": project_id,
        "agent_id": agent_id,
        "mode": str(mode or ""),
        "estimated_context_tokens": int(max(0, estimated_context_tokens)),
        "prompt_tokens": int(max(0, prompt_tokens)),
        "total_tokens": int(max(0, total_tokens)),
    }
    p = token_io_path(project_id, agent_id)
    with p.open("a", encoding="utf-8") as f:
        import json

        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _split_seed_block(content: str) -> tuple[str, str]:
    marker = "### SYSTEM_SEED"
    if not str(content or "").startswith(marker):
        return "", str(content or "")
    end = content.find("\n---\n")
    if end == -1:
        return "", str(content or "")
    end += len("\n---\n")
    return content[:end], content[end:]


def _extract_anchor_lines(seed_block: str, max_lines: int = 24) -> list[str]:
    lines = [ln.rstrip() for ln in str(seed_block or "").splitlines()]
    # Keep dense, non-empty directive lines as mission anchor source.
    out = [ln for ln in lines if ln.strip()][:max(1, int(max_lines))]
    return out


def _split_entries(body: str) -> list[str]:
    text = str(body or "")
    parts = re.split(r"(?=^### 📖 Entry )", text, flags=re.M)
    return [p for p in parts if p.strip()]


def _is_high_value_entry(entry: str) -> bool:
    low = str(entry or "").lower()
    keywords = (
        "objective",
        "mission",
        "constraint",
        "non-negotiable",
        "contract",
        "commit",
        "decision",
        "blocker",
        "next action",
        "error",
        "failed",
        "retry",
    )
    return any(k in low for k in keywords)


def _rule_based_summary(old_entries: list[str], seed_block: str) -> str:
    anchor = _extract_anchor_lines(seed_block, max_lines=14)
    hv = [e for e in old_entries if _is_high_value_entry(e)]
    sample = hv[-6:] if hv else old_entries[-4:]
    sample_lines: list[str] = []
    for e in sample:
        first = [ln.strip() for ln in e.splitlines() if ln.strip()]
        if not first:
            continue
        sample_lines.append(f"- {first[0][:220]}")
    lines = [
        "# MEMORY_COMPACTED_V2",
        "Strategy: rule_based",
        f"Archived Entries: {len(old_entries)}",
        "",
        "## Mission Anchor",
    ]
    lines.extend([f"- {x[:220]}" for x in anchor[:10]] or ["- (none)"])
    lines.append("")
    lines.append("## Key Historical Signals")
    lines.extend(sample_lines or ["- (none)"])
    lines.append("")
    return "\n".join(lines)


def _semantic_summary_with_llm(project_id: str, agent_id: str, old_text: str, seed_block: str) -> str | None:
    api_key = str(getattr(runtime_config, "openrouter_api_key", "") or "").strip()
    if not api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except Exception:
        return None
    model = _resolve_compaction_model(project_id, agent_id)
    try:
        llm = ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.2,
            max_tokens=600,
            default_headers={
                "HTTP-Referer": "https://github.com/GodsPlatform",
                "X-Title": "Gods Platform",
            },
        )
        anchor = "\n".join(_extract_anchor_lines(seed_block, max_lines=20))
        snippet = str(old_text or "")[-24000:]
        prompt = (
            "Summarize chronicle history for continuity. Keep concise markdown with sections:\n"
            "1) Mission Anchor (stable constraints)\n2) Done\n3) Open Risks/Blockers\n4) Next Actions.\n"
            "Do not invent facts.\n\n"
            f"[MISSION_SEED]\n{anchor}\n\n[ARCHIVED_HISTORY]\n{snippet}"
        )
        resp = llm.invoke(prompt)
        content = str(getattr(resp, "content", "") or "").strip()
        if not content:
            return None
        lines = ["# MEMORY_COMPACTED_V2", "Strategy: semantic_llm", "", content, ""]
        return "\n".join(lines)
    except Exception:
        return None


def _build_compact_summary(project_id: str, agent_id: str, old_entries: list[str], seed_block: str) -> tuple[str, str]:
    strategy = compact_strategy(project_id)
    old_text = "\n".join(old_entries)
    if strategy == "semantic_llm":
        semantic = _semantic_summary_with_llm(project_id, agent_id, old_text, seed_block)
        if semantic:
            return semantic, "semantic_llm"
    return _rule_based_summary(old_entries, seed_block), "rule_based"


def ensure_compacted(project_id: str, agent_id: str) -> dict[str, Any]:
    p = chronicle_path(project_id, agent_id)
    if not p.exists():
        return {"performed": False, "reason": "chronicle_missing"}
    content = p.read_text(encoding="utf-8")
    total_tokens = _tok_len(content)
    trigger = compact_trigger_tokens(project_id)
    if total_tokens < trigger:
        return {"performed": False, "reason": "under_threshold", "tokens": total_tokens, "trigger": trigger}

    seed_block, body = _split_seed_block(content)
    entries = _split_entries(body)
    if len(entries) <= 1:
        # Single huge block fallback: keep tail window and archive the rest.
        body_text = str(body or "")
        keep_chars = max(8000, int(trigger * 4 * 0.35))
        if len(body_text) <= keep_chars:
            return {"performed": False, "reason": "insufficient_entries", "tokens": total_tokens, "trigger": trigger}
        old_blob = body_text[:-keep_chars]
        kept_blob = body_text[-keep_chars:]
        summary, actual = _build_compact_summary(project_id, agent_id, [old_blob], seed_block)
        ap = archive_path(project_id, agent_id)
        with ap.open("a", encoding="utf-8") as af:
            af.write("\n\n# ARCHIVE_CHUNK\n")
            af.write(f"timestamp={time.time():.3f}\n")
            af.write("entries=1\n\n")
            af.write(old_blob)
            if not old_blob.endswith("\n"):
                af.write("\n")
            af.write("\n---\n")
        new_content = seed_block + summary + "\n\n---\n\n" + kept_blob
        p.write_text(new_content, encoding="utf-8")
        after_tokens = _tok_len(new_content)
        return {
            "performed": True,
            "strategy": actual,
            "tokens_before": total_tokens,
            "tokens_after": after_tokens,
            "trigger": trigger,
            "archived_entries": 1,
            "kept_entries": 1,
        }

    # Keep recent window and always keep high-value entries from older history.
    target_keep = max(1200, int(trigger * 0.35))
    kept: list[str] = []
    used = 0
    for e in reversed(entries):
        t = _tok_len(e)
        if used + t > target_keep:
            continue
        kept.append(e)
        used += t
    kept.reverse()
    keep_set = set(kept)
    old = [e for e in entries if e not in keep_set]
    if not old:
        return {"performed": False, "reason": "no_old_entries", "tokens": total_tokens, "trigger": trigger}

    summary, actual = _build_compact_summary(project_id, agent_id, old, seed_block)

    ap = archive_path(project_id, agent_id)
    with ap.open("a", encoding="utf-8") as af:
        af.write("\n\n# ARCHIVE_CHUNK\n")
        af.write(f"timestamp={time.time():.3f}\n")
        af.write(f"entries={len(old)}\n\n")
        af.write("".join(old))
        if not str(old[-1]).endswith("\n"):
            af.write("\n")
        af.write("\n---\n")

    new_body = summary + "\n\n---\n\n" + "".join(kept)
    new_content = seed_block + new_body
    p.write_text(new_content, encoding="utf-8")
    after_tokens = _tok_len(new_content)
    return {
        "performed": True,
        "strategy": actual,
        "tokens_before": total_tokens,
        "tokens_after": after_tokens,
        "trigger": trigger,
        "archived_entries": len(old),
        "kept_entries": len(kept),
    }


def load_chronicle_for_context(project_id: str, agent_id: str, fallback: str = "") -> str:
    # Build-time guard: keep prompt chronicle bounded by token trigger before injection.
    ensure_compacted(project_id, agent_id)
    p = chronicle_path(project_id, agent_id)
    if not p.exists():
        return str(fallback or "")
    return p.read_text(encoding="utf-8")
