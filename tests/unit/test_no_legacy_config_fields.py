from gods.config.models import ProjectConfig


def test_project_config_no_legacy_fields():
    cfg = ProjectConfig()
    assert not hasattr(cfg, "inbox_event_enabled")
    assert not hasattr(cfg, "queue_idle_heartbeat_sec")
