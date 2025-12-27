"""FastAPI application entry point."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import engine
from app.routers import (
    admin_exports,
    admin_imports,
    admin_meta,
    admin_versions,
    ai,
    analytics,
    appointments,
    attachments,
    audit,
    auth,
    booking,
    campaigns,
    cases,
    cases_import,
    compliance,
    dashboard,
    dev,
    email_templates,
    integrations,
    internal,
    intended_parents,
    invites,
    jobs,
    matches,
    metadata,
    mfa,
    notes,
    notifications,
    ops,
    permissions,
    pipelines,
    queues,
    settings as settings_router,
    tasks,
    templates,
    tracking,
    webhooks,
    websocket as ws_router,
    workflows,
)

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

# Auth router (always mounted)
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# Cases module routers
app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(notes.router, tags=["notes"])  # Mixed paths: /cases/{id}/notes and /notes/{id}
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

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
app.include_router(internal.router)

# Analytics endpoints (manager dashboards)
app.include_router(analytics.router)

# Ops endpoints (integration health, alerts)
app.include_router(ops.router)

# AI Assistant endpoints
app.include_router(ai.router)

# Dashboard widgets
app.include_router(dashboard.router)

# User Integrations (Gmail, Zoom OAuth)
app.include_router(integrations.router)

# Audit Trail (Manager+)
app.include_router(audit.router)

# Compliance (Retention, Legal Holds)
app.include_router(compliance.router)

# Pipeline Configuration (Developer only)
app.include_router(pipelines.router)

# Permission Management (Manager+)
app.include_router(permissions.router)

# Matches (Surrogate ↔ Intended Parent pairing)
app.include_router(matches.router)

# Automation Workflows (Manager+)
app.include_router(workflows.router)  # Router already has prefix="/workflows"

# Campaigns (Bulk email sends - Manager+)
app.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])

# Workflow Templates (Marketplace - Manager+)
app.include_router(templates.router)

app.include_router(admin_meta.router)  # Already has prefix in router definition

# Admin Versions (Developer-only)
app.include_router(admin_versions.router)

# Admin Exports (Developer-only)
app.include_router(admin_exports.router)

# Admin Imports (Developer-only)
app.include_router(admin_imports.router)

# Metadata API (Picklists - any authenticated user)
app.include_router(metadata.router, prefix="/metadata", tags=["metadata"])

# WebSocket for real-time notifications
app.include_router(ws_router.router)

# Queue Management (Case Routing)
app.include_router(queues.router, prefix="/queues", tags=["queues"])

# File Attachments
app.include_router(attachments.router, tags=["attachments"])

# Team Invitations
app.include_router(invites.router, tags=["invites"])

# Settings (organization and user preferences)
app.include_router(settings_router.router, tags=["settings"])

# Appointments (internal, authenticated)
app.include_router(appointments.router, prefix="/appointments", tags=["appointments"])

# Public Booking (unauthenticated)
app.include_router(booking.router, prefix="/book", tags=["booking"])

# Email Tracking (public endpoints for pixel/click tracking)
app.include_router(tracking.router)

# MFA (Multi-Factor Authentication)
app.include_router(mfa.router, prefix="/mfa", tags=["mfa"])

# Dev router (ONLY mounted in dev mode)
if settings.ENV == "dev":
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
