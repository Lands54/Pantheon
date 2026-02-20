"""Janus sequential strategy: implementing the mindless assembly scheme."""
from __future__ import annotations

import re
import time
from typing import Any
from gods.janus.models import ContextBuildRequest, ContextBuildResult
from gods.mnemosyne.facade import (
    estimate_cards_tokens,
    record_janus_compaction_base_intent,
    save_janus_snapshot,
)

class SequentialV1Strategy:
    _BASE_SEQ_RE = re.compile(r"base_intent_seq\s*=\s*(\d+)")

    @staticmethod
    def _card_seq(card: dict[str, Any]) -> int:
        row = dict(card or {})
        return int(row.get("source_intent_seq_max", row.get("source_seq", -1)) or -1)

    @classmethod
    def _extract_base_seq(cls, card: dict[str, Any]) -> int:
        meta = dict((card or {}).get("meta", {}) or {})
        payload = dict(meta.get("payload", {}) or {}) if isinstance(meta.get("payload"), dict) else {}
        if "base_intent_seq" in payload:
            try:
                return int(payload.get("base_intent_seq", -1) or -1)
            except Exception:
                pass
        if "supersedes_seq" in payload:
            try:
                return int(payload.get("supersedes_seq", -1) or -1)
            except Exception:
                pass
        text = str((card or {}).get("text", "") or "")
        m = cls._BASE_SEQ_RE.search(text)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return -1
        return -1

    @classmethod
    def _is_summary_card(cls, card: dict[str, Any]) -> bool:
        meta = dict((card or {}).get("meta", {}) or {})
        ik = str(meta.get("intent_key", "") or "").strip()
        cid = str((card or {}).get("card_id", "") or "")
        if ik == "janus.compaction.base":
            return True
        if cid.startswith("derived.summary:"):
            return True
        text = str((card or {}).get("text", "") or "")
        return "[JANUS_COMPACTION_BASE]" in text or "[COMPACTED_BASE]" in text

    @classmethod
    def _pick_latest_summary(cls, cards: list[dict[str, Any]]) -> dict[str, Any] | None:
        summaries: list[dict[str, Any]] = []
        for c in list(cards or []):
            if cls._is_summary_card(c):
                summaries.append(c)
        if not summaries:
            return None
        summaries.sort(
            key=lambda x: (
                cls._extract_base_seq(x),
                cls._card_seq(x),
                float(x.get("created_at", 0.0) or 0.0),
            ),
            reverse=True,
        )
        return dict(summaries[0])

    @staticmethod
    def _normalize_kind(kind: str, meta: dict[str, Any]) -> str:
        k = str(kind or "").strip().lower()
        if k in {"task", "event", "mailbox", "tool", "chronicle_summary", "policy", "derived"}:
            return k
        if k in {"inbox", "outbox", "mail"}:
            return "mailbox"
        if k in {"phase", "agent"}:
            return "policy"
        if k == "llm":
            return "chronicle_summary"
        ik = str(meta.get("intent_key", "") or "").strip()
        if ik.startswith("inbox.") or ik.startswith("outbox."):
            return "mailbox"
        if ik.startswith("tool."):
            return "tool"
        if ik.startswith("phase.") or ik.startswith("agent."):
            return "policy"
        if ik == "llm.response":
            return "chronicle_summary"
        return "event"

    @staticmethod
    def _to_snapshot_card(card: dict[str, Any]) -> dict[str, Any]:
        row = dict(card or {})
        seq = int(row.get("source_intent_seq_max", row.get("source_seq", -1)) or -1)
        meta = dict(row.get("meta", {}) or {})
        source_ids = [str(x).strip() for x in list(row.get("source_intent_ids", []) or []) if str(x).strip()]
        if not source_ids and seq > 0:
            source_ids = [f"intent:{seq}"]
        return {
            "card_id": str(row.get("card_id", "") or f"card:{int(time.time() * 1000)}"),
            "kind": SequentialV1Strategy._normalize_kind(str(row.get("kind", "event") or "event"), meta),
            "text": str(row.get("text", "") or ""),
            "source_intent_ids": source_ids,
            "source_intent_seq_max": int(seq),
            "derived_from_card_ids": list(row.get("derived_from_card_ids", []) or []),
            "supersedes_card_ids": list(row.get("supersedes_card_ids", []) or []),
            "compression_type": str(row.get("compression_type", "") or ""),
            "meta": meta,
            "created_at": float(row.get("created_at", time.time()) or time.time()),
        }

    @staticmethod
    def _persist_arranged_cards(req: ContextBuildRequest, cards: list[dict[str, Any]]) -> None:
        normalized = [SequentialV1Strategy._to_snapshot_card(c) for c in list(cards or []) if isinstance(c, dict)]
        if not normalized:
            return
        base_seq = max([int(c.get("source_intent_seq_max", 0) or 0) for c in normalized] or [0])
        now = time.time()
        try:
            save_janus_snapshot(
                req.project_id,
                req.agent_id,
                {
                    "snapshot_id": f"snap_{req.agent_id}_{int(now)}",
                    "project_id": req.project_id,
                    "agent_id": req.agent_id,
                    "base_intent_seq": int(max(0, base_seq)),
                    "token_estimate": int(estimate_cards_tokens(normalized)),
                    "cards": normalized,
                    "dropped": [],
                    "created_at": now,
                    "updated_at": now,
                },
            )
        except Exception:
            return

    def build(self, req: ContextBuildRequest) -> ContextBuildResult:
        materials = req.context_materials
        
        # Determine N from config or default to 10
        n_recent = int(req.context_cfg.get("n_recent", 10))
        token_limit = int(req.context_cfg.get("token_budget_chronicle_trigger", 8000))
        
        # 1. Use our smart recomposer to get the core cards grouped by role
        # We simulate the recompose logic here to separate chronicle for compression
        fixed_start_keys = {"material.profile", "material.directives", "material.task_state"}
        fixed_end_keys = {"material.mailbox", "material.tools", "material.inbox_hint"}
        
        static_start: list[dict[str, Any]] = []
        static_end: list[dict[str, Any]] = []
        context_cards: list[dict[str, Any]] = []
        
        if hasattr(materials, "cards"):
            for c in materials.cards:
                seq = self._card_seq(c)
                ik = str(c.get("meta", {}).get("intent_key", "") or "")
                if seq == -1:
                    if ik in fixed_start_keys: static_start.append(c)
                    elif ik in fixed_end_keys or ik.startswith("material.mailbox"): static_end.append(c)
                    else: static_start.append(c)
                else:
                    context_cards.append(c)
        
        context_cards.sort(key=self._card_seq)

        # Apply summary-base slicing:
        # latest summary + (base_seq, ...] context cards
        latest_summary = self._pick_latest_summary(context_cards)
        base_seq = self._extract_base_seq(latest_summary) if latest_summary else -1
        non_summary_cards: list[dict[str, Any]] = []
        for c in context_cards:
            if self._is_summary_card(c):
                continue
            if self._card_seq(c) <= base_seq:
                continue
            non_summary_cards.append(c)
        non_summary_cards.sort(key=self._card_seq)
        
        # Split into chronicle and recents
        n = max(0, n_recent)
        if len(non_summary_cards) <= n:
            chronicle = []
            recents = non_summary_cards
        else:
            chronicle = non_summary_cards[:-n]
            recents = non_summary_cards[-n:]

        # 2. Check and Perform Compression on Chronicle
        chronicle_tokens = self._estimate_tokens(chronicle)
        compress_meta = {"triggered": False}
        
        if chronicle and chronicle_tokens > token_limit:
            summary_card = self._compress_chronicle(req, chronicle)
            if summary_card:
                latest_summary = summary_card
                chronicle = []
                compress_meta = {
                    "triggered": True, 
                    "before_tokens": chronicle_tokens,
                    "after_tokens": self._estimate_tokens([summary_card]),
                    "base_seq": int(summary_card.get("source_intent_seq_max", 0) or 0),
                }

        # 3. Assemble Ordered Cards
        middle: list[dict[str, Any]] = []
        if latest_summary is not None:
            middle.append(latest_summary)
        middle.extend(chronicle)
        middle.extend(recents)
        ordered_cards = static_start + middle + static_end

        # 4. Build system blocks
        blocks: list[str] = []
        if req.directives:
            blocks.append(f"## CORE DIRECTIVES\n{req.directives}")

        has_tools_card = False
        for card in ordered_cards:
            text = str(card.get("text", "") or "").strip()
            if text:
                blocks.append(text)
            ik = str((card.get("meta", {}) or {}).get("intent_key", "") or "")
            if ik == "material.tools":
                has_tools_card = True

        if (not has_tools_card) and req.tools_desc:
            blocks.append(f"## AVAILABLE TOOLS\n{req.tools_desc}")

        self._persist_arranged_cards(req, ordered_cards)

        return ContextBuildResult(
            strategy_used="sequential_v1",
            system_blocks=blocks,
            token_usage={"total": 0, "chronicle": self._estimate_tokens(chronicle)},
            preview={"card_count": len(ordered_cards), "compression": compress_meta}
        )

    def _estimate_tokens(self, cards: list[dict[str, Any]]) -> int:
        return sum(len(str(c.get("text", ""))) // 4 for c in cards)

    def _compress_chronicle(self, req: ContextBuildRequest, cards: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Call LLM to summarize a chunk of history cards."""
        brain = None
        if req.agent and hasattr(req.agent, "brain"):
            brain = req.agent.brain
        else:
            try:
                from gods.agents.brain import GodBrain
                brain = GodBrain(agent_id=req.agent_id, project_id=req.project_id)
            except Exception:
                pass
        
        if not brain:
            return None
            
        text_to_summarize = "\n\n".join([f"[{c.get('kind','event')}] {c.get('text','')}" for c in cards])
        
        prompt = (
            "You are a memory consolidation module. Below is a detailed log of past events and actions. "
            "Compress them into a single, high-density summary. Keep technical decisions, key results, and major blockers. "
            "Discard minor details or repetitive logs. Be extremely concise.\n\n"
            f"--- LOGS TO SUMMARIZE ---\n{text_to_summarize}\n\n"
            "SUMMARY:"
        )
        
        try:
            from langchain_core.messages import HumanMessage
            # Use think or think_with_tools
            if hasattr(brain, "think"):
                summary_text = brain.think(prompt, trace_meta={"purpose": "context_compression", "agent_id": req.agent_id})
            elif hasattr(brain, "think_with_tools"):
                response = brain.think_with_tools(
                    [HumanMessage(content=prompt)],
                    tools=[], 
                    trace_meta={"purpose": "context_compression", "agent_id": req.agent_id}
                )
                summary_text = str(response.content or "").strip()
            else:
                return None

            summary_text = str(summary_text or "").strip()
            if not summary_text or "ERROR" in summary_text.upper():
                return None
            base_seq = max([self._card_seq(c) for c in list(cards or [])] or [0])
            source_card_ids = [str(c.get("card_id", "") or "").strip() for c in list(cards or []) if str(c.get("card_id", "") or "").strip()]
            source_intent_ids: list[str] = []
            for c in list(cards or []):
                source_intent_ids.extend([str(x).strip() for x in list(c.get("source_intent_ids", []) or []) if str(x).strip()])
            source_intent_ids = sorted(set(source_intent_ids))
            intent_id = ""
            intent_seq = 0
            try:
                row = record_janus_compaction_base_intent(
                    req.project_id,
                    req.agent_id,
                    summary_text,
                    base_seq,
                    source_card_ids=source_card_ids,
                )
                intent_id = str(row.get("intent_id", "") or "")
                intent_seq = int(row.get("intent_seq", 0) or 0)
            except Exception:
                pass
            if intent_id:
                source_intent_ids.append(intent_id)
            source_intent_ids = sorted(set(source_intent_ids))
            summary_text_block = f"[JANUS_COMPACTION_BASE]\nbase_intent_seq={base_seq}\n{summary_text}"
            return {
                "card_id": f"derived.summary:{int(time.time())}",
                "kind": "derived",
                "text": summary_text_block,
                "source_intent_ids": source_intent_ids or ([f"intent:{base_seq}"] if base_seq > 0 else []),
                "source_intent_seq_max": int(max(base_seq, intent_seq)),
                "derived_from_card_ids": source_card_ids,
                "supersedes_card_ids": source_card_ids,
                "compression_type": "llm_summarize",
                "meta": {
                    "is_summary": True,
                    "intent_key": "janus.compaction.base",
                    "payload": {
                        "base_intent_seq": int(base_seq),
                        "source_card_ids": source_card_ids,
                    },
                    "count": len(cards),
                },
            }
        except Exception:
            return None
