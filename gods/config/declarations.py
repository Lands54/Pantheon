"""Config declaration contracts and validators (SSOT for config metadata/defaults)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import copy

_ALLOWED_TYPES = {"string", "integer", "number", "boolean", "object", "array"}


@dataclass(frozen=True)
class ConfigFieldDecl:
    key: str
    scope: str  # system | project | agent
    type: str  # string | integer | number | boolean | object | array
    default: Any
    nullable: bool
    description: str
    owner: str
    runtime_used_by: list[str]
    status: str = "active"  # active | deprecated
    enum: list[str] | None = None
    constraints: dict[str, Any] | None = None
    ui: dict[str, Any] | None = None


@dataclass(frozen=True)
class ConfigBlockDecl:
    module_id: str
    module_title: str
    scope: str  # system | project | agent
    group_id: str
    group_title: str
    fields: list[ConfigFieldDecl]
    default_collapsed: bool = False


def _expect_type(value: Any, expected: str) -> bool:
    if value is None:
        return True
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return False


def validate_declaration_blocks(blocks: list[ConfigBlockDecl]) -> None:
    seen: set[tuple[str, str]] = set()
    for b in blocks:
        if b.scope not in {"system", "project", "agent"}:
            raise ValueError(f"invalid block scope: {b.module_id} -> {b.scope}")
        if not str(b.module_id or "").strip():
            raise ValueError("block.module_id is required")
        if not str(b.module_title or "").strip():
            raise ValueError(f"block.module_title is required: {b.module_id}")
        if not str(b.group_id or "").strip():
            raise ValueError(f"block.group_id is required: {b.module_id}")
        if not str(b.group_title or "").strip():
            raise ValueError(f"block.group_title is required: {b.module_id}")

        for f in list(b.fields or []):
            if f.scope != b.scope:
                raise ValueError(f"scope mismatch for {f.scope}.{f.key} in block {b.module_id}")
            if f.type not in _ALLOWED_TYPES:
                raise ValueError(f"invalid type for {f.scope}.{f.key}: {f.type}")
            if f.status not in {"active", "deprecated"}:
                raise ValueError(f"invalid status for {f.scope}.{f.key}: {f.status}")
            if not str(f.description or "").strip():
                raise ValueError(f"description required for {f.scope}.{f.key}")
            if not str(f.owner or "").strip():
                raise ValueError(f"owner required for {f.scope}.{f.key}")
            if f.status == "active" and not list(f.runtime_used_by or []):
                raise ValueError(f"runtime_used_by required for active field {f.scope}.{f.key}")
            if f.default is None and not f.nullable:
                raise ValueError(f"default cannot be null for non-nullable {f.scope}.{f.key}")
            if f.default is not None and not _expect_type(f.default, f.type):
                raise ValueError(
                    f"default type mismatch for {f.scope}.{f.key}: expected {f.type}, got {type(f.default).__name__}"
                )
            sk = (f.scope, f.key)
            if sk in seen:
                raise ValueError(f"duplicate declaration key: {f.scope}.{f.key}")
            seen.add(sk)


def build_default_maps(blocks: list[ConfigBlockDecl]) -> dict[str, dict[str, Any]]:
    out = {"system": {}, "project": {}, "agent": {}}
    for b in blocks:
        for f in b.fields:
            out[b.scope][f.key] = copy.deepcopy(f.default)
    return out


def build_groups(blocks: list[ConfigBlockDecl]) -> list[dict[str, Any]]:
    order: list[tuple[str, str]] = []
    group_map: dict[tuple[str, str], dict[str, Any]] = {}
    for b in blocks:
        gk = (b.scope, b.group_id)
        if gk not in group_map:
            order.append(gk)
            group_map[gk] = {
                "id": b.group_id,
                "title": b.group_title,
                "scope": b.scope,
                "keys": [],
                "default_collapsed": bool(b.default_collapsed),
            }
        gm = group_map[gk]
        if b.default_collapsed:
            gm["default_collapsed"] = True
        for f in b.fields:
            if f.key not in gm["keys"]:
                gm["keys"].append(f.key)

    out: list[dict[str, Any]] = []
    for gk in order:
        row = dict(group_map[gk])
        if not row.get("default_collapsed"):
            row.pop("default_collapsed", None)
        out.append(row)
    return out


def build_module_groups(blocks: list[ConfigBlockDecl]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in blocks:
        out.append(
            {
                "id": b.module_id,
                "title": b.module_title,
                "scope": b.scope,
                "group_id": b.group_id,
                "group_title": b.group_title,
                "default_collapsed": bool(b.default_collapsed),
                "keys": [f.key for f in b.fields],
            }
        )
    return out
