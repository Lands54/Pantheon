import importlib
import pytest


def test_no_legacy_state_window_path_helper():
    paths = importlib.import_module("gods.paths")
    assert not hasattr(paths, "legacy_agent_state_window_path")


def test_no_legacy_state_window_store_module():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("gods.agents.state_window_store")


def test_no_legacy_runtime_registry_module():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("gods.agents.runtime.registry")
