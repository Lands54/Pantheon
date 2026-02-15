"""Configuration use-case service."""
from __future__ import annotations

from typing import Any

from gods.config import ProjectConfig, get_available_agents, runtime_config
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
        proj = runtime_config.projects.get(runtime_config.current_project)
        if not proj:
            runtime_config.projects["default"] = ProjectConfig()
            proj = runtime_config.projects["default"]

        return {
            "openrouter_api_key": self.mask_api_key(runtime_config.openrouter_api_key),
            "has_openrouter_api_key": bool(runtime_config.openrouter_api_key),
            "current_project": runtime_config.current_project,
            "enable_legacy_social_api": runtime_config.enable_legacy_social_api,
            "deprecated": {
                "enable_legacy_social_api": "deprecated-compat",
                "projects.*.autonomous_parallel": "deprecated-noop",
            },
            "projects": runtime_config.projects,
            "available_agents": get_available_agents(),
            "all_tools": [t.name for t in GODS_TOOLS],
        }

    def save_config_payload(self, data: dict[str, Any]) -> dict[str, str]:
        if "openrouter_api_key" in data:
            incoming = str(data["openrouter_api_key"] or "")
            # Prevent masked values from GET /config being written back as real secrets.
            if "*" not in incoming:
                runtime_config.openrouter_api_key = incoming
        if "current_project" in data:
            runtime_config.current_project = data["current_project"]
        if "enable_legacy_social_api" in data:
            runtime_config.enable_legacy_social_api = bool(data["enable_legacy_social_api"])
        if "projects" in data:
            for pid, pdata in data["projects"].items():
                runtime_config.projects[pid] = ProjectConfig(**pdata)

        runtime_config.save()
        return {"status": "success"}


config_service = ConfigService()
