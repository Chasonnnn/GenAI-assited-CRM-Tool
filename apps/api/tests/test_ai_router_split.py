def test_ai_router_modules_exist():
    from app.routers import (
        ai_settings,
        ai_consent,
        ai_chat,
        ai_conversations,
        ai_actions,
        ai_usage,
        ai_focus,
        ai_workflows,
        ai_schedule,
        ai_tasks,
    )

    modules = [
        ai_settings,
        ai_consent,
        ai_chat,
        ai_conversations,
        ai_actions,
        ai_usage,
        ai_focus,
        ai_workflows,
        ai_schedule,
        ai_tasks,
    ]

    for module in modules:
        assert hasattr(module, "router")
