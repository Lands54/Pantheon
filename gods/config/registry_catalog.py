"""Registry catalog built from declarative config blocks (SSOT)."""
from __future__ import annotations

from gods.config.blocks import ALL_CONFIG_BLOCKS
from gods.config.declarations import build_groups, build_module_groups
from gods.config.registry import ConfigEntry, ConfigRegistry


def build_registry() -> ConfigRegistry:
    fields: dict[str, list[ConfigEntry]] = {"system": [], "project": [], "agent": []}

    for block in ALL_CONFIG_BLOCKS:
        for f in block.fields:
            fields[f.scope].append(
                ConfigEntry(
                    key=f.key,
                    scope=f.scope,
                    type=f.type,
                    nullable=f.nullable,
                    default=f.default,
                    description=f.description,
                    owner=f.owner,
                    runtime_used_by=list(f.runtime_used_by or []),
                    status=f.status,
                    enum=f.enum,
                    constraints=f.constraints,
                    ui=f.ui,
                    module_id=block.module_id,
                )
            )

    return ConfigRegistry(
        version="2.0.0",
        fields=fields,
        groups=build_groups(ALL_CONFIG_BLOCKS),
        module_groups=build_module_groups(ALL_CONFIG_BLOCKS),
    )


CONFIG_REGISTRY = build_registry()
