from __future__ import annotations


def test_angelia_facade_surface():
    from gods.angelia import facade

    assert hasattr(facade, "enqueue_event")
    assert hasattr(facade, "list_events")
    assert hasattr(facade, "inject_inbox_after_action_if_any")


def test_iris_facade_surface():
    from gods.iris import facade

    assert hasattr(facade, "enqueue_message")
    assert hasattr(facade, "fetch_inbox_context")
    assert hasattr(facade, "list_outbox_receipts")


def test_hermes_facade_surface():
    from gods.hermes import facade

    assert hasattr(facade, "register_protocol")
    assert hasattr(facade, "invoke")
    assert hasattr(facade, "route")


def test_mnemosyne_facade_surface():
    from gods.mnemosyne import facade

    assert hasattr(facade, "write_entry")
    assert hasattr(facade, "list_entries")
    assert hasattr(facade, "read_entry")


def test_janus_facade_surface():
    from gods.janus import facade

    assert hasattr(facade, "context_preview")
    assert hasattr(facade, "context_reports")


def test_runtime_facade_surface():
    from gods.runtime import facade

    assert hasattr(facade, "detach_submit")
    assert hasattr(facade, "docker_available")
    assert hasattr(facade, "resolve_execution_backend")
