"""Declarative config registry for zero-compat strict mode."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


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
    def __init__(self, *, version: str, fields: dict[str, list[ConfigEntry]], groups: list[dict[str, Any]]):
        self.version = version
        self.fields = fields
        self.groups = groups
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
        for scope in ("system", "project", "agent"):
            for e in self.entries(scope):
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

        return {
            "deprecated": deprecated,
            "unreferenced": unreferenced,
            "naming_conflicts": naming_conflicts,
        }
