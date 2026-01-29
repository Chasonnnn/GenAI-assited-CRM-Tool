"""AI Assistant API router (aggregated sub-routers)."""

from fastapi import APIRouter

from app.routers import (
    ai_actions,
    ai_chat,
    ai_consent,
    ai_conversations,
    ai_focus,
    ai_schedule,
    ai_settings,
    ai_tasks,
    ai_usage,
    ai_workflows,
)

router = APIRouter(prefix="/ai", tags=["AI"])

router.include_router(ai_settings.router)
router.include_router(ai_consent.router)
router.include_router(ai_chat.router)
router.include_router(ai_conversations.router)
router.include_router(ai_actions.router)
router.include_router(ai_usage.router)
router.include_router(ai_focus.router)
router.include_router(ai_workflows.router)
router.include_router(ai_schedule.router)
router.include_router(ai_tasks.router)
