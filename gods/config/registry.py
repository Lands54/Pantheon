"""Declarative config registry for zero-compat strict mode."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
from itertools import combinations


@dataclass(frozen=True)
class ConfigEntry:
    key: str
    scope: str  # system | project | agent
    type: str  # string | integer | number | boolean | object | array
    nullable: bool
    default: Any
    description: str
    owner: str
    runtime_used_by: list[str]
    status: str = "active"  # active | deprecated
    enum: list[str] | None = None
    constraints: dict[str, Any] | None = None
    ui: dict[str, Any] | None = None
    module_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        if out.get("enum") is None:
            out.pop("enum", None)
        if out.get("constraints") is None:
            out.pop("constraints", None)
        if out.get("ui") is None:
            out.pop("ui", None)
        return out


class ConfigRegistry:
    def __init__(
        self,
        *,
        version: str,
        fields: dict[str, list[ConfigEntry]],
        groups: list[dict[str, Any]],
        module_groups: list[dict[str, Any]] | None = None,
    ):
        self.version = version
        self.fields = fields
        self.groups = groups
        self.module_groups = list(module_groups or [])
        self._index: dict[tuple[str, str], ConfigEntry] = {}
        for scope, entries in fields.items():
            for e in entries:
                self._index[(scope, e.key)] = e

    def entries(self, scope: str) -> list[ConfigEntry]:
        return list(self.fields.get(scope, []))

    def get(self, scope: str, key: str) -> ConfigEntry | None:
        return self._index.get((scope, key))

    def export_schema(self, *, tool_options: list[str]) -> dict[str, Any]:
        deprecations: list[dict[str, Any]] = []
        for scope in ("system", "project", "agent"):
            for e in self.entries(scope):
                if e.status == "deprecated":
                    deprecations.append(
                        {
                            "scope": scope,
                            "key": e.key,
                            "description": e.description,
                        }
                    )

        return {
            "version": self.version,
            "scopes": ["system", "project", "agent"],
            "fields": {
                "system": [e.to_dict() for e in self.entries("system")],
                "project": [e.to_dict() for e in self.entries("project")],
                "agent": [e.to_dict() for e in self.entries("agent")],
            },
            "groups": self.groups,
            "module_groups": self.module_groups,
            "tool_options": list(tool_options),
            "deprecations": deprecations,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _expect_type(value: Any, expected: str) -> bool:
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
        return True

    def _validate_entry(self, entry: ConfigEntry, value: Any, where: str) -> list[str]:
        warnings: list[str] = []
        if value is None:
            if entry.nullable:
                if entry.status == "deprecated":
                    warnings.append(f"deprecated config used: {where}")
                return warnings
            raise ValueError(f"invalid config '{where}': null is not allowed")

        if not self._expect_type(value, entry.type):
            raise ValueError(f"invalid config '{where}': expected {entry.type}")

        if entry.enum and isinstance(value, str) and value not in entry.enum:
            allowed = ", ".join(entry.enum)
            raise ValueError(f"invalid config '{where}': expected one of [{allowed}]")

        if entry.key == "metis_refresh_mode" and isinstance(value, str) and value.strip().lower() == "node":
            warnings.append(
                f"config normalized: {where}=node is ignored under sequential_v1 and will run as pulse"
            )

        cons = entry.constraints or {}
        if entry.type in {"integer", "number"}:
            if "min" in cons and float(value) < float(cons["min"]):
                raise ValueError(f"invalid config '{where}': must be >= {cons['min']}")
            if "max" in cons and float(value) > float(cons["max"]):
                raise ValueError(f"invalid config '{where}': must be <= {cons['max']}")

        if entry.status == "deprecated":
            warnings.append(f"deprecated config used: {where}")

        return warnings

    def validate_payload(self, data: dict[str, Any]) -> list[str]:
        if not isinstance(data, dict):
            raise ValueError("invalid config payload: must be object")

        allowed_root = {"openrouter_api_key", "current_project", "projects"}
        unknown_root = [k for k in data.keys() if k not in allowed_root]
        if unknown_root:
            raise ValueError(f"invalid config payload: unknown top-level keys: {', '.join(sorted(unknown_root))}")

        warnings: list[str] = []

        for root_key in ("openrouter_api_key", "current_project"):
            if root_key in data:
                e = self.get("system", root_key)
                if not e:
                    raise ValueError(f"registry missing system entry for '{root_key}'")
                warnings.extend(self._validate_entry(e, data[root_key], root_key))

        if "projects" in data:
            projects = data["projects"]
            if not isinstance(projects, dict):
                raise ValueError("invalid config 'projects': expected object")
            for pid, proj in projects.items():
                if not isinstance(proj, dict):
                    raise ValueError(f"invalid config 'projects.{pid}': expected object")

                for key, value in proj.items():
                    if key == "agent_settings":
                        if not isinstance(value, dict):
                            raise ValueError(f"invalid config 'projects.{pid}.agent_settings': expected object")
                        for aid, cfg in value.items():
                            if not isinstance(cfg, dict):
                                raise ValueError(f"invalid config 'projects.{pid}.agent_settings.{aid}': expected object")
                            for agent_key, agent_value in cfg.items():
                                ae = self.get("agent", agent_key)
                                if not ae:
                                    raise ValueError(
                                        f"invalid config 'projects.{pid}.agent_settings.{aid}.{agent_key}': unknown key"
                                    )
                                warnings.extend(
                                    self._validate_entry(
                                        ae,
                                        agent_value,
                                        f"projects.{pid}.agent_settings.{aid}.{agent_key}",
                                    )
                                )
                        continue

                    pe = self.get("project", key)
                    if not pe:
                        raise ValueError(f"invalid config 'projects.{pid}.{key}': unknown key")
                    warnings.extend(self._validate_entry(pe, value, f"projects.{pid}.{key}"))

        return warnings

    def audit_usage(self) -> dict[str, Any]:
        deprecated: list[dict[str, str]] = []
        unreferenced: list[dict[str, str]] = []
        all_entries: list[ConfigEntry] = []
        for scope in ("system", "project", "agent"):
            for e in self.entries(scope):
                all_entries.append(e)
                if e.status == "deprecated":
                    deprecated.append({"scope": scope, "key": e.key})
                if not e.runtime_used_by:
                    unreferenced.append({"scope": scope, "key": e.key})

        naming_conflicts: list[dict[str, str]] = []
        keys = {e.key for scope in ("project", "agent", "system") for e in self.entries(scope)}
        if "mailbox" in keys and ("inbox" in keys or "outbox" in keys):
            naming_conflicts.append(
                {
                    "topic": "mailbox-naming",
                    "detail": "Detected mailbox/inbox/outbox top-level naming overlap; verify semantic boundary.",
                }
            )

        # Detect fields sharing many lexical tokens (possible semantic overlap).
        semantic_overlaps: list[dict[str, Any]] = []
        project_entries = [e for e in all_entries if e.scope == "project"]

        def _tokens(k: str) -> set[str]:
            return {x for x in str(k or "").lower().split("_") if x}

        for a, b in combinations(project_entries, 2):
            ta = _tokens(a.key)
            tb = _tokens(b.key)
            inter = ta & tb
            if len(inter) < 2:
                continue
            union = ta | tb
            score = float(len(inter)) / float(max(1, len(union)))
            if score < 0.5:
                continue
            semantic_overlaps.append(
                {
                    "scope": "project",
                    "keys": sorted([a.key, b.key]),
                    "shared_tokens": sorted(inter),
                    "score": round(score, 3),
                }
            )
        semantic_overlaps = sorted(
            semantic_overlaps,
            key=lambda x: (float(x.get("score", 0.0)), ",".join(x.get("keys", []))),
            reverse=True,
        )[:40]

        # Detect strongly coupled fields by shared runtime consumer modules.
        by_module: dict[str, list[tuple[str, str]]] = {}
        for e in all_entries:
            for mod in list(e.runtime_used_by or []):
                m = str(mod or "").strip()
                if not m:
                    continue
                by_module.setdefault(m, []).append((e.scope, e.key))
        coupled_fields: list[dict[str, Any]] = []
        for mod, refs in by_module.items():
            uniq = sorted({f"{s}.{k}" for s, k in refs})
            if len(uniq) < 2:
                continue
            coupled_fields.append(
                {
                    "module": mod,
                    "count": len(uniq),
                    "fields": uniq[:20],
                }
            )
        coupled_fields = sorted(coupled_fields, key=lambda x: int(x.get("count", 0)), reverse=True)[:60]

        # Detect fields not covered by UI groups.
        grouped: set[tuple[str, str]] = set()
        for g in list(self.groups or []):
            scope = str(g.get("scope", "") or "").strip()
            for k in list(g.get("keys", []) or []):
                grouped.add((scope, str(k or "").strip()))
        ungrouped_fields: list[dict[str, str]] = []
        for e in all_entries:
            if (e.scope, e.key) in grouped:
                continue
            ungrouped_fields.append({"scope": e.scope, "key": e.key})

        module_quality: list[dict[str, Any]] = []
        by_module: dict[str, list[ConfigEntry]] = {}
        for e in all_entries:
            mod = str(e.module_id or "unknown").strip() or "unknown"
            by_module.setdefault(mod, []).append(e)
        for mod, entries in by_module.items():
            deprecated_count = sum(1 for e in entries if e.status == "deprecated")
            missing_desc = sum(1 for e in entries if not str(e.description or "").strip())
            missing_runtime = sum(
                1 for e in entries if e.status != "deprecated" and not list(e.runtime_used_by or [])
            )
            module_quality.append(
                {
                    "module": mod,
                    "fields": len(entries),
                    "deprecated": deprecated_count,
                    "missing_description": missing_desc,
                    "missing_runtime_used_by": missing_runtime,
                }
            )
        module_quality = sorted(module_quality, key=lambda x: str(x.get("module", "")))

        return {
            "deprecated": deprecated,
            "unreferenced": unreferenced,
            "naming_conflicts": naming_conflicts,
            "semantic_overlaps": semantic_overlaps,
            "coupled_fields": coupled_fields,
            "ungrouped_fields": ungrouped_fields,
            "module_quality": module_quality,
        }
