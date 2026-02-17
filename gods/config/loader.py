"""Config IO and migration helpers."""
from __future__ import annotations

import json
import logging

from gods.config.defaults import default_projects
from gods.config.models import CONFIG_FILE, SystemConfig
from gods.config.validation import normalize_system_config

logger = logging.getLogger("GodsConfig")


def save_system_config(cfg: SystemConfig) -> None:
    normalized = normalize_system_config(cfg)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(normalized.model_dump_json(indent=4))


def load_system_config() -> SystemConfig:
    if not CONFIG_FILE.exists():
        cfg = SystemConfig(projects=default_projects())
        return normalize_system_config(cfg)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "projects" not in data:
            raise ValueError("legacy config payload is not supported; expected top-level 'projects'")

        cfg = SystemConfig(**data)
        cfg = normalize_system_config(cfg)
        return cfg
    except Exception as e:
        logger.error("Failed to load config.json in strict mode: %s", e)
        raise RuntimeError(f"invalid config.json under zero-compat strict mode: {e}") from e
