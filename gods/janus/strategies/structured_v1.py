"""Structured Janus context strategy with strict card-only pipeline."""
from __future__ import annotations

import time
from typing import Any

from gods.janus.models import ContextBuildRequest, ContextBuildResult
from gods.janus.strategy_base import ContextStrategy
from gods.mnemosyne.facade import (
    build_cards_from_intent_views,
    estimate_cards_tokens,
    load_janus_snapshot,
    record_janus_compaction_base_intent,
    record_snapshot_compression,
    save_janus_snapshot,
    validate_card_buckets,
)


def _tok_len(text: str) -> int:
    return max(1, len(text) // 4)


def _clip_by_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _render_cards(cards: list[dict[str, Any]], token_budget: int) -> tuple[str, int]:
    lines: list[str] = []
    used = 0
    for c in list(cards or []):
        text = str((c or {}).get("text", "") or "").strip()
        if not text:
            continue
        t = _tok_len(text)
        if used + t > token_budget:
            continue
        used += t
        kind = str((c or {}).get("kind", "") or "")
        cid = str((c or {}).get("card_id", "") or "")
        lines.append(f"[{kind}:{cid}] {text}")
    if not lines:
        return "(no card memory)", 0
    return "\n".join(lines), used


class StructuredV1ContextStrategy(ContextStrategy):
    name = "structured_v1"

    def _merge_cards(self, base_cards: list[dict[str, Any]], delta_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for c in list(base_cards or []):
            cid = str(c.get("card_id", "") or "")
            if cid:
                merged[cid] = dict(c)
        for c in list(delta_cards or []):
            cid = str(c.get("card_id", "") or "")
            if not cid:
                continue
            current = merged.get(cid)
            if not isinstance(current, dict):
                merged[cid] = dict(c)
                continue
            source_ids = sorted(
                set([str(x) for x in list(current.get("source_intent_ids", []) or []) if str(x)])
                | set([str(x) for x in list(c.get("source_intent_ids", []) or []) if str(x)])
            )
            current["source_intent_ids"] = source_ids
            current["source_intent_seq_max"] = max(int(current.get("source_intent_seq_max", 0) or 0), int(c.get("source_intent_seq_max", 0) or 0))
            current["text"] = str(c.get("text", "") or current.get("text", ""))
            current["kind"] = str(c.get("kind", current.get("kind", "event")) or "event")
            current["meta"] = dict(current.get("meta", {}) or {})
            current["meta"].update(dict(c.get("meta", {}) or {}))
            merged[cid] = current
        cards = list(merged.values())
        cards.sort(key=lambda x: (int(x.get("source_intent_seq_max", 0) or 0), float(x.get("created_at", 0.0) or 0.0)), reverse=True)
        return cards

    def _flatten_bucket_cards(self, card_buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in ("profile", "task_state", "mailbox", "events", "policy"):
            rows.extend([dict(x) for x in list(card_buckets.get(key, []) or []) if isinstance(x, dict)])
        return rows

    def _resolve_cards_from_chaos(self, req: ContextBuildRequest, materials: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        legacy_keys = {
            "chronicle",
            "chronicle_index_entries",
            "chronicle_index_rendered",
            "context_index_entries",
            "context_index_rendered",
            "triggers_rendered",
            "mailbox_rendered",
            "profile",
            "task_state",
        }
        if "card_buckets" not in materials:
            legacy_hits = sorted([k for k in legacy_keys if k in materials])
            if legacy_hits:
                raise ValueError(
                    "JANUS_CARD_BUCKETS_REQUIRED: missing context_materials.card_buckets under zero-compat mode; "
                    f"legacy keys found: {', '.join(legacy_hits)}"
                )
            raise ValueError("JANUS_CARD_BUCKETS_REQUIRED: context_materials.card_buckets is required")

        buckets = validate_card_buckets(dict(materials.get("card_buckets") or {}))
        latest_seq = int(materials.get("intent_seq_latest", 0) or 0)

        loaded = load_janus_snapshot(req.project_id, req.agent_id)
        snapshot_base_seq = 0
        if isinstance(loaded, dict):
            try:
                snapshot_base_seq = int(loaded.get("base_intent_seq", 0) or 0)
            except Exception:
                snapshot_base_seq = 0
        short_k = max(10, int((req.context_cfg or {}).get("short_window_intents", 120) or 120))
        split_seq = max(0, latest_seq - short_k)
        semantic_cards = build_cards_from_intent_views(
            req.project_id,
            req.agent_id,
            split_intent_seq=split_seq,
            to_intent_seq=latest_seq,
            long_limit=4000,
            short_limit=3000,
        )
        if snapshot_base_seq > 0:
            semantic_cards = [
                c
                for c in semantic_cards
                if not (
                    str((c.get("meta", {}) or {}).get("memory_span", "") or "") == "long"
                    and int(c.get("source_intent_seq_max", 0) or 0) < snapshot_base_seq
                )
            ]

        cards = self._merge_cards(semantic_cards, self._flatten_bucket_cards(buckets))
        return cards, {
            "loaded": bool(loaded),
            "base_intent_seq": max(split_seq, snapshot_base_seq),
            "latest_intent_seq": latest_seq,
            "delta_cards": len([c for c in semantic_cards if int(c.get("source_intent_seq_max", 0) or 0) > split_seq]),
        }

    def _compress_chronicle_with_llm(self, req: ContextBuildRequest, long_cards: list[dict[str, Any]]) -> tuple[str, str]:
        lines: list[str] = []
        for c in list(long_cards or []):
            text = str(c.get("text", "") or "").strip()
            if not text:
                continue
            cid = str(c.get("card_id", "") or "")
            lines.append(f"[{cid}] {text}")
        source_text = "\n".join(lines)[-28000:]
        if not source_text:
            return "", "empty_long_cards"
        prompt = (
            "你是 Janus Chronicle 压缩器。请压缩以下历史上下文，输出中文 markdown，严格遵守：\n"
            "1) 只保留事实，不编造；\n"
            "2) 输出四段：已完成、当前状态、未决风险、下一步；\n"
            "3) 150-350 字；\n"
            "4) 不输出代码块。\n\n"
            f"[CHRONICLE_SOURCE]\n{source_text}"
        )
        try:
            from gods.agents.brain import GodBrain
            brain = GodBrain(agent_id=req.agent_id, project_id=req.project_id)
            content = str(brain.think(prompt, trace_meta={"mode": "janus_compaction"} ) or "").strip()
            if not content or content.startswith("Error in reasoning:") or content.startswith("❌ ERROR:"):
                return "", "llm_unavailable"
            return content, "llm"
        except Exception:
            return "", "llm_exception"

    def _record_compaction_base_intent(
        self,
        req: ContextBuildRequest,
        summary: str,
        source_cards: list[dict[str, Any]],
    ) -> int:
        if not str(summary or "").strip():
            return 0
        source_ids = [str(c.get("card_id", "") or "").strip() for c in list(source_cards or []) if str(c.get("card_id", "") or "").strip()]
        base = int(max([int(c.get("source_intent_seq_max", 0) or 0) for c in list(source_cards or [])] or [0]))
        try:
            rec = record_janus_compaction_base_intent(
                project_id=req.project_id,
                agent_id=req.agent_id,
                summary=str(summary or ""),
                base_intent_seq=base,
                source_card_ids=source_ids,
            )
            return int(rec.get("intent_seq", 0) or 0)
        except Exception:
            return 0

    def compress_cards_if_needed(
        self,
        cards: list[dict[str, Any]],
        token_budget_total: int,
        req: ContextBuildRequest | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        current = list(cards or [])
        before = estimate_cards_tokens(current)
        dropped: list[dict[str, Any]] = []
        if before <= token_budget_total:
            return current, dropped, {"compressed": False, "before_tokens": before, "after_tokens": before}

        work = list(current)
        long_cards = [
            c
            for c in work
            if str((c.get("meta", {}) or {}).get("memory_span", "") or "") == "long"
            and not str(c.get("card_id", "") or "").startswith("material.")
        ]
        summary = ""
        compress_mode = ""
        if req is not None:
            summary, compress_mode = self._compress_chronicle_with_llm(req, long_cards)
        base_intent_seq = 0
        if summary:
            base_intent_seq = self._record_compaction_base_intent(req, summary, long_cards)
            if base_intent_seq > 0:
                work = [
                    c for c in work
                    if not (
                        str((c.get("meta", {}) or {}).get("memory_span", "") or "") == "long"
                        and int(c.get("source_intent_seq_max", 0) or 0) < base_intent_seq
                    )
                ]
                work.append(
                    {
                        "card_id": f"intent.short:{req.agent_id}:{base_intent_seq}",
                        "kind": "chronicle_summary",
                        "text": f"[COMPACTED_BASE]\nbase_intent_seq={base_intent_seq}\n{summary}",
                        "source_intent_ids": [f"{req.agent_id}:{base_intent_seq}"],
                        "source_intent_seq_max": int(base_intent_seq),
                        "derived_from_card_ids": [str(c.get("card_id", "") or "") for c in long_cards if str(c.get("card_id", "") or "")],
                        "supersedes_card_ids": [str(c.get("card_id", "") or "") for c in long_cards if str(c.get("card_id", "") or "")],
                        "compression_type": "llm_chronicle_base",
                        "meta": {"memory_span": "short"},
                        "created_at": time.time(),
                    }
                )

        groups = ["chronicle_summary", "event", "mailbox", "tool"]
        for kind in groups:
            if estimate_cards_tokens(work) <= token_budget_total:
                break
            bucket = [
                c for c in work
                if str(c.get("kind", "") or "") == kind and not str(c.get("card_id", "")).startswith("material.")
            ]
            if len(bucket) < 2:
                continue
            merged_source_ids: list[str] = []
            merged_source_set = set()
            merged_card_ids: list[str] = []
            text_lines: list[str] = []
            seq_max = 0
            for c in bucket:
                cid = str(c.get("card_id", "") or "")
                if cid:
                    merged_card_ids.append(cid)
                for sid in list(c.get("source_intent_ids", []) or []):
                    s = str(sid)
                    if s and s not in merged_source_set:
                        merged_source_set.add(s)
                        merged_source_ids.append(s)
                seq_max = max(seq_max, int(c.get("source_intent_seq_max", 0) or 0))
                text = str(c.get("text", "") or "").strip()
                if text:
                    text_lines.append(text)
            if not text_lines:
                continue
                
            limit_merge = max(8, token_budget_total // 2)
            used_merge = 0
            kept_lines = []
            for txt in text_lines:
                t = _tok_len(txt)
                if used_merge + t > limit_merge:
                    break
                kept_lines.append(txt)
                used_merge += t
            kept_lines.reverse()
            summary_text = "; ".join(kept_lines)

            derived_id = f"derived:{kind}:{int(time.time() * 1000)}"
            derived = {
                "card_id": derived_id,
                "kind": "derived",
                "text": summary_text,
                "source_intent_ids": merged_source_ids,
                "source_intent_seq_max": seq_max,
                "derived_from_card_ids": merged_card_ids,
                "supersedes_card_ids": merged_card_ids,
                "compression_type": "merge",
                "meta": {"derived_kind": kind},
                "created_at": time.time(),
            }
            work = [c for c in work if c not in bucket]
            work.append(derived)
            dropped.append({"reason": "compressed_merge", "kind": kind, "superseded_card_ids": merged_card_ids})

        work.sort(key=lambda x: (int(x.get("source_intent_seq_max", 0) or 0), float(x.get("created_at", 0.0) or 0.0)), reverse=True)
        after = estimate_cards_tokens(work)
        if after > token_budget_total:
            clipped: list[dict[str, Any]] = []
            used = 0
            for c in work:
                t = _tok_len(str(c.get("text", "") or ""))
                if used + t > token_budget_total:
                    dropped.append({"reason": "token_budget", "card_id": str(c.get("card_id", "") or "")})
                    continue
                clipped.append(c)
                used += t
            work = clipped
            after = estimate_cards_tokens(work)
        return work, dropped, {
            "compressed": True,
            "before_tokens": before,
            "after_tokens": after,
            "compaction_base_intent_seq": int(base_intent_seq),
            "compaction_mode": str(compress_mode or ""),
        }

    def persist_snapshot(
        self,
        req: ContextBuildRequest,
        cards: list[dict[str, Any]],
        dropped: list[dict[str, Any]],
        latest_intent_seq: int,
        compress_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        snapshot = {
            "snapshot_id": f"snap_{req.agent_id}_{int(now)}",
            "project_id": req.project_id,
            "agent_id": req.agent_id,
            "base_intent_seq": int(max(0, int((compress_meta or {}).get("compaction_base_intent_seq", 0) or 0), latest_intent_seq)),
            "token_estimate": int(estimate_cards_tokens(cards)),
            "cards": list(cards or []),
            "dropped": list(dropped or []),
            "created_at": now,
            "updated_at": now,
        }
        res = save_janus_snapshot(req.project_id, req.agent_id, snapshot)
        derived_cards = [c for c in list(cards or []) if str(c.get("kind", "") or "") == "derived"]
        if derived_cards or list(dropped or []):
            record_snapshot_compression(
                req.project_id,
                req.agent_id,
                {
                    "snapshot_id": snapshot["snapshot_id"],
                    "base_intent_seq": int(snapshot.get("base_intent_seq", 0) or 0),
                    "before_tokens": int((compress_meta or {}).get("before_tokens", snapshot.get("token_estimate", 0)) or 0),
                    "after_tokens": int((compress_meta or {}).get("after_tokens", snapshot.get("token_estimate", 0)) or 0),
                    "compressed": bool((compress_meta or {}).get("compressed", False)),
                    "derived_count": len(derived_cards),
                    "derived": [
                        {
                            "card_id": str(c.get("card_id", "") or ""),
                            "derived_from_card_ids": list(c.get("derived_from_card_ids", []) or []),
                            "supersedes_card_ids": list(c.get("supersedes_card_ids", []) or []),
                            "source_intent_ids": list(c.get("source_intent_ids", []) or []),
                        }
                        for c in derived_cards
                    ],
                    "dropped": list(dropped or []),
                    "timestamp": now,
                },
            )
        return res

    def build(self, req: ContextBuildRequest) -> ContextBuildResult:
        cfg = req.context_cfg
        total_budget = int(cfg.get("token_budget_total", 32000))

        materials = dict(req.context_materials or req.state.get("__context_materials", {}) or {})
        cards, card_meta = self._resolve_cards_from_chaos(req, materials)
        cards, dropped, compress_meta = self.compress_cards_if_needed(cards, token_budget_total=total_budget, req=req)
        card_block, card_tokens = _render_cards(cards, token_budget=total_budget)

        latest_seq_for_snapshot = int(
            max(
                int(card_meta.get("latest_intent_seq", card_meta.get("base_intent_seq", 0)) or 0),
                int((compress_meta or {}).get("compaction_base_intent_seq", 0) or 0),
            )
        )
        self.persist_snapshot(
            req,
            cards,
            dropped,
            latest_intent_seq=latest_seq_for_snapshot,
            compress_meta=compress_meta,
        )

        system_blocks = []
        if str(req.directives or "").strip():
            system_blocks.append(f"# DIRECTIVES\n{str(req.directives).strip()}")
            
        if str(req.local_memory or "").strip():
            system_blocks.append(f"# LOCAL_MEMORY\n{str(req.local_memory).strip()}")
            
        system_blocks.append(f"# CARD_CONTEXT\n{card_block}")
            
        if str(req.inbox_hint or "").strip() and bool(cfg.get("include_inbox_status_hints", True)):
            system_blocks.append(f"# INBOX_STATUS\n{str(req.inbox_hint).strip()}")
            
        pn = str(req.phase_name or "").strip().upper() or "EXECUTION"
        if str(req.phase_block or "").strip():
            system_blocks.append(f"# PHASE_{pn}\n{str(req.phase_block).strip()}")
            
        if str(req.tools_desc or "").strip():
            system_blocks.append(f"# TOOLS_AVAILABLE\n{str(req.tools_desc).strip()}")

        usage = {
            "combined_memory_tokens": _tok_len("\n\n".join(system_blocks)),
            "task_tokens": _tok_len(str(req.directives or "")),
            "mailbox_tokens": _tok_len(str(req.inbox_hint or "")),
            "card_tokens": card_tokens,
            "cards_count": len(cards),
            "chronicle_tokens": 0,
            "context_index_tokens": 0,
        }
        preview = {
            "mode": self.name,
            "phase": req.phase_name,
            "snapshot_loaded": bool(card_meta.get("loaded", False)),
            "snapshot_base_intent_seq": int(card_meta.get("base_intent_seq", 0) or 0),
            "snapshot_delta_cards": int(card_meta.get("delta_cards", 0) or 0),
            "cards_compressed": bool(compress_meta.get("compressed", False)),
            "cards_before_tokens": int(compress_meta.get("before_tokens", 0) or 0),
            "cards_after_tokens": int(compress_meta.get("after_tokens", 0) or 0),
            "cards_dropped": len(dropped),
            "compaction_mode": str(compress_meta.get("compaction_mode", "") or ""),
            "compaction_base_intent_seq": int(compress_meta.get("compaction_base_intent_seq", 0) or 0),
        }
        return ContextBuildResult(
            strategy_used=self.name,
            system_blocks=system_blocks,
            token_usage=usage,
            preview=preview,
        )
