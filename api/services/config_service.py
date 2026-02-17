"""Configuration use-case service."""
from __future__ import annotations

from typing import Any

from gods.config import (
    get_available_agents,
    runtime_config,
    snapshot_runtime_config_payload,
    apply_runtime_config_payload,
)
from gods.tools import GODS_TOOLS


class ConfigService:
    @staticmethod
    def mask_api_key(raw: str) -> str:
        token = (raw or "").strip()
        if not token:
            return ""
        if len(token) <= 4:
            return "*" * len(token)
        return f"{'*' * (len(token) - 4)}{token[-4:]}"

    def get_config_payload(self) -> dict[str, Any]:
        # Safety net: ensure current project always resolves.
        _ = snapshot_runtime_config_payload()

        return {
            "openrouter_api_key": self.mask_api_key(runtime_config.openrouter_api_key),
            "has_openrouter_api_key": bool(runtime_config.openrouter_api_key),
            "current_project": runtime_config.current_project,
            "projects": runtime_config.projects,
            "available_agents": get_available_agents(),
            "all_tools": [t.name for t in GODS_TOOLS],
        }

    def save_config_payload(self, data: dict[str, Any]) -> dict[str, str]:
        apply_runtime_config_payload(data)
        return {"status": "success"}


config_service = ConfigService()
