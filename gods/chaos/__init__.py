"""Chaos resource aggregation layer."""
from gods.chaos.contracts import ResourceSnapshot


def build_resource_snapshot(*args, **kwargs):
    from gods.chaos.snapshot import build_resource_snapshot as _impl

    return _impl(*args, **kwargs)


def pull_incremental_materials(*args, **kwargs):
    from gods.chaos.snapshot import pull_incremental_materials as _impl

    return _impl(*args, **kwargs)

__all__ = ["ResourceSnapshot", "build_resource_snapshot", "pull_incremental_materials"]
