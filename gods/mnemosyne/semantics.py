"""Unified semantic service for Mnemosyne."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from gods.paths import mnemosyne_dir

logger = logging.getLogger(__name__)


class SemanticsService:
    _instance: SemanticsService | None = None

    def __init__(self):
        self._intents: dict[str, Any] = {}
        self._materials: dict[str, Any] = {}
        self._prefixes: dict[str, Any] = {}
        self._tools: list[str] = []
        self._version: int = 0
        self.reload()

    @classmethod
    def get_instance(cls) -> SemanticsService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reload(self):
        """Hot-reload semantic definitions from semantics.json."""
        path = Path(__file__).parent / "semantics.json"
        if not path.exists():
            logger.error(f"semantics.json not found at {path}")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._intents = data.get("intents", {})
            self._materials = data.get("materials", {})
            self._prefixes = data.get("prefixes", {})
            self._tools = data.get("tools", [])
            self._version = data.get("version", 0)
            logger.info(f"Semantics reloaded. Version: {self._version}")
        except Exception as e:
            logger.error(f"Failed to reload semantics: {e}")

    def get_intent_definition(self, key: str) -> dict[str, Any] | None:
        return self._intents.get(key)

    def list_intent_keys(self) -> list[str]:
        keys = list(self._intents.keys())
        for tool in self._tools:
            keys.append(f"tool.{tool}.ok")
            keys.append(f"tool.{tool}.error")
            keys.append(f"tool.{tool}.blocked")
        return sorted(set(keys))

    def is_registered_intent(self, key: str) -> bool:
        if key in self._intents:
            return True
        if key.startswith("tool."):
            parts = key.split(".")
            if len(parts) == 3 and parts[1] in self._tools and parts[2] in {"ok", "error", "blocked"}:
                return True
        return False

    def get_policy(self, key: str) -> dict[str, Any] | None:
        defn = self.get_intent_definition(key)
        if defn:
            p = dict(defn.get("policy", {}))
            templates = defn.get("templates", {})
            p["chronicle_template_key"] = templates.get("chronicle", "")
            p["runtime_log_template_key"] = templates.get("runtime_log", "")
            p["llm_context_template_key"] = templates.get("llm_context", "")
            return p
        
        if key.startswith("tool."):
            parts = key.split(".")
            status = parts[-1]
            if status == "ok":
                return {
                    "to_chronicle": True, "to_runtime_log": False, "to_llm_context": False,
                    "chronicle_template_key": "memory_tool_ok",
                    "runtime_log_template_key": "",
                    "llm_context_template_key": ""
                }
            elif status == "error":
                return {
                    "to_chronicle": True, "to_runtime_log": True, "to_llm_context": True,
                    "chronicle_template_key": "memory_tool_error",
                    "runtime_log_template_key": "memory_tool_error",
                    "llm_context_template_key": "memory_tool_error"
                }
            else:
                return {
                    "to_chronicle": False, "to_runtime_log": True, "to_llm_context": True,
                    "chronicle_template_key": "",
                    "runtime_log_template_key": "",
                    "llm_context_template_key": ""
                }
        return {
            "to_chronicle": False, "to_runtime_log": True, "to_llm_context": False,
            "chronicle_template_key": "", "runtime_log_template_key": "", "llm_context_template_key": ""
        }

    def get_schema(self, key: str) -> dict[str, list[str]]:
        defn = self.get_intent_definition(key)
        if defn:
            return defn.get("schema", {"guaranteed": [], "optional": []})
        if key.startswith("tool."):
            return {"guaranteed": ["tool_name", "status", "args", "result", "result_compact"], "optional": []}
        if key.startswith("event."):
            return {"guaranteed": ["stage", "event_id", "event_type", "priority", "attempt", "max_attempts", "payload"], "optional": []}
        return {"guaranteed": [], "optional": []}

    def is_valid_material(self, card_id: str) -> bool:
        if card_id in self._materials:
            return True
        for prefix in self._prefixes:
            if card_id.startswith(prefix):
                return True
        return False

    def get_tool_names(self) -> list[str]:
        return list(self._tools)

    def get_template_key(self, intent_key: str, scope: Literal["runtime_log", "chronicle", "llm_context"]) -> str:
        defn = self.get_intent_definition(intent_key)
        if not defn:
            if intent_key.startswith("tool."):
                status = intent_key.split(".")[-1]
                return f"memory_tool_{status}"
            return ""
        return defn.get("templates", {}).get(scope, "")

semantics_service = SemanticsService.get_instance()
