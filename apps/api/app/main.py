"""FastAPI application entry point."""
import logging
import os

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

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter



# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="CRM API",
    description="Multi-tenant CRM and case management API",
    version=settings.VERSION,
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
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

from app.routers import cases_import
app.include_router(cases_import.router)  # Already has /cases/import prefix

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

# Dashboard widgets
from app.routers import dashboard
app.include_router(dashboard.router)

# User Integrations (Gmail, Zoom OAuth)
from app.routers import integrations
app.include_router(integrations.router)

# Audit Trail (Manager+)
from app.routers import audit
app.include_router(audit.router)

# Compliance (Retention, Legal Holds)
from app.routers import compliance
app.include_router(compliance.router)

# Pipeline Configuration (Developer only)
from app.routers import pipelines
app.include_router(pipelines.router)

# Permission Management (Manager+)
from app.routers import permissions
app.include_router(permissions.router)

# Matches (Surrogate ↔ Intended Parent pairing)
from app.routers import matches
app.include_router(matches.router)

# Automation Workflows (Manager+)
from app.routers import workflows
app.include_router(workflows.router)  # Router already has prefix="/workflows"

# Campaigns (Bulk email sends - Manager+)
from app.routers import campaigns
app.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])

# Workflow Templates (Marketplace - Manager+)
from app.routers import templates
app.include_router(templates.router)

from app.routers import admin_meta
app.include_router(admin_meta.router)  # Already has prefix in router definition

# Admin Versions (Developer-only)
from app.routers import admin_versions
app.include_router(admin_versions.router)

# Admin Exports (Developer-only)
from app.routers import admin_exports
app.include_router(admin_exports.router)

# Metadata API (Picklists - any authenticated user)
from app.routers import metadata
app.include_router(metadata.router, prefix="/metadata", tags=["metadata"])

# WebSocket for real-time notifications
from app.routers import websocket as ws_router
app.include_router(ws_router.router)

# Queue Management (Case Routing)
from app.routers import queues
app.include_router(queues.router, prefix="/queues", tags=["queues"])

# File Attachments
from app.routers import attachments
app.include_router(attachments.router, tags=["attachments"])

# Team Invitations
from app.routers import invites
app.include_router(invites.router, tags=["invites"])

# Settings (organization and user preferences)
from app.routers import settings as settings_router
app.include_router(settings_router.router, tags=["settings"])

# Appointments (internal, authenticated)
from app.routers import appointments
app.include_router(appointments.router, prefix="/appointments", tags=["appointments"])

# Public Booking (unauthenticated)
from app.routers import booking
app.include_router(booking.router, prefix="/book", tags=["booking"])

# Email Tracking (public endpoints for pixel/click tracking)
from app.routers import tracking
app.include_router(tracking.router)

# MFA (Multi-Factor Authentication)
from app.routers import mfa
app.include_router(mfa.router, prefix="/mfa", tags=["mfa"])

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
    return {"status": "ok", "env": settings.ENV, "version": settings.VERSION}
