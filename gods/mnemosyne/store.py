"""Mnemosyne archival storage for project-scoped durable knowledge."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

VALID_VAULTS = {"agent", "human", "system"}


def _root(project_id: str) -> Path:
    p = Path("projects") / project_id / "mnemosyne"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _vault_dir(project_id: str, vault: str) -> Path:
    if vault not in VALID_VAULTS:
        raise ValueError(f"invalid vault: {vault}")
    p = _root(project_id) / vault
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path(project_id: str, vault: str) -> Path:
    return _vault_dir(project_id, vault) / "entries.jsonl"


def _entry_path(project_id: str, vault: str, entry_id: str) -> Path:
    return _vault_dir(project_id, vault) / "entries" / f"{entry_id}.md"


def write_entry(project_id: str, vault: str, author: str, title: str, content: str, tags: list[str] | None = None) -> dict[str, Any]:
    if not title.strip():
        raise ValueError("title is required")
    entry_id = f"m_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
    now = time.time()
    tags = [str(t).strip() for t in (tags or []) if str(t).strip()]

    md_path = _entry_path(project_id, vault, entry_id)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_text = (
        f"# {title.strip()}\n\n"
        f"- entry_id: {entry_id}\n"
        f"- author: {author.strip()}\n"
        f"- vault: {vault}\n"
        f"- created_at: {now}\n"
        f"- tags: {', '.join(tags) if tags else ''}\n\n"
        f"---\n\n{content}\n"
    )
    md_path.write_text(md_text, encoding="utf-8")

    row = {
        "entry_id": entry_id,
        "title": title.strip(),
        "author": author.strip(),
        "vault": vault,
        "project_id": project_id,
        "tags": tags,
        "created_at": now,
        "path": str(md_path),
    }
    idx = _index_path(project_id, vault)
    with idx.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def list_entries(project_id: str, vault: str, limit: int = 50) -> list[dict[str, Any]]:
    idx = _index_path(project_id, vault)
    if not idx.exists():
        return []
    out: list[dict[str, Any]] = []
    with idx.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    lim = max(1, min(int(limit), 500))
    return out[-lim:]


def read_entry(project_id: str, vault: str, entry_id: str) -> dict[str, Any] | None:
    entries = list_entries(project_id, vault, limit=10000)
    hit = None
    for e in entries:
        if e.get("entry_id") == entry_id:
            hit = e
            break
    if not hit:
        return None
    p = Path(str(hit.get("path", "")))
    if not p.exists():
        return None
    return {
        "meta": hit,
        "content": p.read_text(encoding="utf-8"),
    }
