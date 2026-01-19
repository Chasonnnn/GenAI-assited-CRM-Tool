"""API routers."""

from app.routers.auth import router as auth_router
from app.routers.surrogates import router as surrogates_router
from app.routers.notes import router as notes_router
from app.routers.tasks import router as tasks_router
from app.routers.webhooks import router as webhooks_router
from app.routers.internal import router as internal_router
from app.routers.analytics import router as analytics_router
from app.routers.ops import router as ops_router
from app.routers.monitoring import router as monitoring_router

__all__ = [
    "auth_router",
    "surrogates_router",
    "notes_router",
    "tasks_router",
    "webhooks_router",
    "internal_router",
    "analytics_router",
    "ops_router",
    "monitoring_router",
]
