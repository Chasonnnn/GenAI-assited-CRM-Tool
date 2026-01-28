import pytest


def test_prompt_registry_renders_schedule_parse():
    from app.services.ai_prompt_registry import get_prompt

    prompt = get_prompt("schedule_parse")
    rendered = prompt.render_user(reference_date="2026-01-01", text="Test schedule")

    assert "2026-01-01" in rendered
    assert "Test schedule" in rendered
    assert prompt.version


def test_prompt_registry_renders_workflow_generation():
    from app.services.ai_prompt_registry import get_prompt

    prompt = get_prompt("workflow_generation")
    rendered = prompt.render_user(
        triggers="trigger",
        actions="action",
        templates="template",
        users="users",
        stages="stages",
        user_input="Build a workflow",
    )

    assert "trigger" in rendered
    assert "action" in rendered
    assert "template" in rendered
    assert "users" in rendered
    assert "stages" in rendered
    assert "Build a workflow" in rendered


def test_prompt_registry_invalid_key_raises():
    from app.services.ai_prompt_registry import get_prompt

    with pytest.raises(KeyError):
        get_prompt("unknown_key")
