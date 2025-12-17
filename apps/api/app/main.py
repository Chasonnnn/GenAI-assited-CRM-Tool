"""FastAPI application entry point."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

# ============================================================================
# Sentry Integration (optional, for production error tracking)
# ============================================================================

if settings.SENTRY_DSN and settings.ENV != "dev":
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of requests for performance monitoring
        send_default_pii=False,  # Don't send PII to Sentry
    )
    logging.info("Sentry initialized for error tracking")

# ============================================================================
# Rate Limiting
# ============================================================================

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="CRM API",
    description="Multi-tenant CRM and case management API",
    version="0.5.0",
    docs_url="/docs" if settings.ENV == "dev" else None,
    redoc_url="/redoc" if settings.ENV == "dev" else None,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - must be added before routers
# Tightened for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,  # Required for cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=["X-Request-ID"],
)

# ============================================================================
# Routers
# ============================================================================

from app.routers import auth, cases, notes, tasks, webhooks, email_templates, jobs, intended_parents, notifications

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

# Audit Trail (Manager+)
from app.routers import audit
app.include_router(audit.router)

# Pipeline Configuration (Manager+)
from app.routers import pipelines
app.include_router(pipelines.router)

# Admin Versions (Developer-only)
from app.routers import admin_versions
app.include_router(admin_versions.router)

# Dev router (ONLY mounted in dev mode)
if settings.ENV == "dev":
    from app.routers import dev
    app.include_router(dev.router, prefix="/dev", tags=["dev"])


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
def health():
    """
    Health check endpoint.
    
    Verifies database connectivity and returns environment info.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "env": settings.ENV, "version": "0.5.0"}