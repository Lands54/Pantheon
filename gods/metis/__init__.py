"""Metis strategy module facade."""
from gods.metis.contracts import ResourceSnapshot, RuntimeEnvelope, StrategySpec
from gods.metis.strategy_specs import (
    export_strategy_default_tools,
    export_strategy_phase_map,
    get_strategy_spec,
    list_strategy_specs,
)


def build_resource_snapshot(*args, **kwargs):
    from gods.metis.snapshot import build_resource_snapshot_via_chaos

    return build_resource_snapshot_via_chaos(*args, **kwargs)


def build_runtime_envelope(*args, **kwargs):
    from gods.metis.snapshot import build_runtime_envelope as _impl

    return _impl(*args, **kwargs)


def refresh_runtime_envelope(*args, **kwargs):
    from gods.metis.snapshot import refresh_runtime_envelope as _impl

    return _impl(*args, **kwargs)


def resolve_refresh_mode(*args, **kwargs):
    from gods.metis.snapshot import resolve_refresh_mode as _impl

    return _impl(*args, **kwargs)

__all__ = [
    "ResourceSnapshot",
    "RuntimeEnvelope",
    "StrategySpec",
    "build_resource_snapshot",
    "build_runtime_envelope",
    "refresh_runtime_envelope",
    "resolve_refresh_mode",
    "get_strategy_spec",
    "list_strategy_specs",
    "export_strategy_phase_map",
    "export_strategy_default_tools",
]
