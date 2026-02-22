"""Chaos contracts for resource aggregation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields, replace
import re
from typing import Any


@dataclass(frozen=True)
class MemoryMaterials:
    """Static context materials fed into Janus (PulseLedger is dynamic source)."""

    profile: str = ""
    directives: str = ""
    task_state: str = ""
    tools: str = ""
    inbox_hint: str = ""


@dataclass(frozen=True)
class ResourceSnapshot:
    """Immutable snapshot of strategy materials prepared by Chaos."""

    project_id: str
    agent_id: str
    strategy: str
    events: list[dict[str, Any]] = field(default_factory=list)
    mailbox: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    contracts: dict[str, Any] = field(default_factory=dict)
    tool_catalog: list[str] = field(default_factory=list)
    config_view: dict[str, Any] = field(default_factory=dict)
    context_materials: MemoryMaterials = field(default_factory=lambda: MemoryMaterials())
    runtime_meta: dict[str, Any] = field(default_factory=dict)

    def update(self, **patch: Any) -> "ResourceSnapshot":
        """Return a new snapshot with patched fields (immutable update)."""
        allowed = {f.name for f in fields(self)}
        unknown = [k for k in patch.keys() if k not in allowed]
        if unknown:
            raise ValueError(f"unknown ResourceSnapshot field(s): {', '.join(sorted(unknown))}")

        merged: dict[str, Any] = {}
        for key, value in patch.items():
            current = getattr(self, key)
            if isinstance(current, dict) and isinstance(value, dict):
                merged[key] = {**current, **value}
            elif isinstance(current, list) and isinstance(value, list):
                merged[key] = list(value)
            else:
                merged[key] = value
        return replace(self, **merged)

    @staticmethod
    def _parse_path(path: str) -> list[str | int]:
        raw = str(path or "").strip()
        if not raw:
            raise ValueError("empty patch path")
        parts: list[str | int] = []
        token = ""
        i = 0
        while i < len(raw):
            ch = raw[i]
            if ch == ".":
                if token:
                    parts.append(token)
                    token = ""
                i += 1
                continue
            if ch == "[":
                if token:
                    parts.append(token)
                    token = ""
                j = raw.find("]", i + 1)
                if j < 0:
                    raise ValueError(f"invalid patch path '{raw}': missing ']'")
                idx_text = raw[i + 1 : j].strip()
                if not re.fullmatch(r"\d+", idx_text):
                    raise ValueError(f"invalid patch path '{raw}': list index must be non-negative int")
                parts.append(int(idx_text))
                i = j + 1
                continue
            token += ch
            i += 1
        if token:
            parts.append(token)
        return parts

    @classmethod
    def _apply_path(cls, data: dict[str, Any], path: str, value: Any) -> None:
        tokens = cls._parse_path(path)
        if not tokens:
            raise ValueError("empty patch tokens")
        root = tokens[0]
        if not isinstance(root, str) or root not in data:
            raise ValueError(f"invalid patch root '{root}' in path '{path}'")
        if len(tokens) == 1:
            data[root] = value
            return

        cur: Any = data[root]
        for idx, tk in enumerate(tokens[1:], start=1):
            is_last = idx == len(tokens) - 1
            if isinstance(tk, int):
                if not isinstance(cur, list):
                    raise ValueError(f"path '{path}' expects list before index [{tk}]")
                if tk < 0 or tk >= len(cur):
                    raise ValueError(f"path '{path}' index out of range: [{tk}]")
                if is_last:
                    cur[tk] = value
                    return
                cur = cur[tk]
                continue

            if not isinstance(cur, dict):
                raise ValueError(f"path '{path}' expects object before key '{tk}'")
            if is_last:
                cur[tk] = value
                return
            if tk not in cur:
                raise ValueError(f"path '{path}' key does not exist: '{tk}'")
            cur = cur[tk]

    def patch_paths(self, patches: dict[str, Any]) -> "ResourceSnapshot":
        if not isinstance(patches, dict) or not patches:
            return self
        base = {f.name: deepcopy(getattr(self, f.name)) for f in fields(self)}
        for path, value in patches.items():
            self._apply_path(base, str(path), value)
        return ResourceSnapshot(**base)

    def patch_path(self, path: str, value: Any) -> "ResourceSnapshot":
        return self.patch_paths({path: value})
