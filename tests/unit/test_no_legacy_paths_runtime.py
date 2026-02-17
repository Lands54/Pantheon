import importlib


def test_no_legacy_state_window_path_helper():
    paths = importlib.import_module("gods.paths")
    assert not hasattr(paths, "legacy_agent_state_window_path")
