"""Config IO and migration helpers."""
from __future__ import annotations

import json
import logging

from gods.config.defaults import default_projects
from gods.config.models import CONFIG_FILE, AgentModelConfig, ProjectConfig, SystemConfig
from gods.config.validation import normalize_system_config

logger = logging.getLogger("GodsConfig")


def save_system_config(cfg: SystemConfig) -> None:
    normalized = normalize_system_config(cfg)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(normalized.model_dump_json(indent=4))


def _migrate_legacy_payload(data: dict) -> SystemConfig:
    logger.warning("Migrating legacy config payload to project-based schema")

    old_active = data.get("active_agents", [])
    old_settings = data.get("agent_settings", {})

    default_proj = ProjectConfig(
        name="Default World",
        active_agents=list(old_active or []),
        agent_settings={
            k: (AgentModelConfig(**v) if isinstance(v, dict) else AgentModelConfig()) for k, v in (old_settings or {}).items()
        },
        simulation_enabled=bool(data.get("simulation_enabled", False)),
        simulation_interval_min=int(data.get("simulation_interval_min", 10)),
        simulation_interval_max=int(data.get("simulation_interval_max", 40)),
        summarize_threshold=int(data.get("summarize_threshold", 12)),
        summarize_keep_count=int(data.get("summarize_keep_count", 5)),
    )
    cfg = SystemConfig(
        openrouter_api_key=str(data.get("openrouter_api_key", "") or ""),
        current_project="default",
        projects={"default": default_proj},
    )
    return normalize_system_config(cfg)


def load_system_config() -> SystemConfig:
    if not CONFIG_FILE.exists():
        cfg = SystemConfig(projects=default_projects())
        return normalize_system_config(cfg)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "projects" not in data:
            cfg = _migrate_legacy_payload(data)
            save_system_config(cfg)
            return cfg

        cfg = SystemConfig(**data)
        cfg = normalize_system_config(cfg)
        return cfg
    except Exception as e:
        logger.error("Failed to load config.json, fallback to defaults: %s", e)
        return normalize_system_config(SystemConfig(projects=default_projects()))
