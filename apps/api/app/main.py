"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.routers import auth, cases, notes, tasks, webhooks, email_templates, jobs, intended_parents, notifications

app = FastAPI(
    title="CRM API",
    description="Multi-tenant CRM and case management API",
    version="0.4.0",
    docs_url="/docs" if settings.ENV == "dev" else None,
    redoc_url="/redoc" if settings.ENV == "dev" else None,
)

# CORS middleware - must be added before routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth router (always mounted)
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# Cases module routers
app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(notes.router, tags=["notes"])  # Mixed paths: /cases/{id}/notes and /notes/{id}
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

# Intended Parents module
app.include_router(intended_parents.router, prefix="/intended-parents", tags=["intended-parents"])

# Notifications (user-scoped)
app.include_router(notifications.router, prefix="/me", tags=["notifications"])

# Email and jobs routers
app.include_router(email_templates.router, prefix="/email-templates", tags=["email"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

# Webhooks (Meta Lead Ads webhook handler)
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

# Internal endpoints (scheduled/cron jobs - protected by INTERNAL_SECRET)
from app.routers import internal
app.include_router(internal.router)

# Analytics endpoints (manager dashboards)
from app.routers import analytics
app.include_router(analytics.router)

# Ops endpoints (integration health, alerts)
from app.routers import ops
app.include_router(ops.router)

# AI Assistant endpoints
from app.routers import ai
app.include_router(ai.router)

# User Integrations (Gmail, Zoom OAuth)
from app.routers import integrations
app.include_router(integrations.router)

# Dev router (ONLY mounted in dev mode)
if settings.ENV == "dev":
    from app.routers import dev
    app.include_router(dev.router, prefix="/dev", tags=["dev"])


@app.get("/health")
def health():
    """
    Health check endpoint.
    
    Verifies database connectivity and returns environment info.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "env": settings.ENV, "version": "0.2.0"}