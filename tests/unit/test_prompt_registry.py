from pathlib import Path

from gods.prompts.registry import PromptRegistry


def test_prompt_registry_renders_default_template():
    registry = PromptRegistry()
    out = registry.render("scheduler_pulse_message", reason="heartbeat")
    assert "heartbeat" in out


def test_prompt_registry_supports_project_override(tmp_path):
    project_id = "prompt_override_test"
    prompt_dir = Path("projects") / project_id / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    custom = prompt_dir / "scheduler_pulse_context.txt"
    custom.write_text("CUSTOM-$reason", encoding="utf-8")

    registry = PromptRegistry()
    out = registry.render("scheduler_pulse_context", project_id=project_id, reason="x")
    assert out == "CUSTOM-x"
