import importlib.util


def test_context_policy_shim_removed():
    spec = importlib.util.find_spec("gods.agents.context_policy")
    assert spec is None


def test_record_memory_event_removed():
    from gods import mnemosyne

    assert not hasattr(mnemosyne, "record_memory_event")
