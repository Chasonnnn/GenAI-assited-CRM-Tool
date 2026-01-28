"""FastAPI application entry point."""

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

try:  # pragma: no cover - depends on installed middleware
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
except Exception:  # pragma: no cover - fallback for older Starlette
    try:
        from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    except Exception:  # pragma: no cover - proxy headers middleware unavailable
        ProxyHeadersMiddleware = None

from app.core.config import settings
from app.core.deps import COOKIE_NAME
from app.core.csrf import CSRF_HEADER, CSRF_COOKIE_NAME, set_csrf_cookie, validate_csrf
from app.core.gcp_monitoring import report_exception, setup_gcp_monitoring
from app.core import migrations as db_migrations
from app.core.protobuf_guard import apply_protobuf_json_depth_guard
from app.core.structured_logging import build_log_context
from app.core.rate_limit import limiter
from app.core.redis_client import get_sync_redis_client
from app.core.telemetry import configure_telemetry
from app.db.session import SessionLocal, engine
from app.db.enums import AlertSeverity, AlertType
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
    custom_fields,
    surrogates,
    surrogates_import,
    compliance,
    dashboard,
    dev,
    email_templates,
    forms,
    forms_public,
    integrations,
    internal,
    import_templates,
    intended_parents,
    interviews,
    invites,
    jobs,
    journey,
    matches,
    metadata,
    mfa,
    monitoring,
    notes,
    notifications,
    oidc,
    ops,
    permissions,
    pipelines,
    platform,
    profile,
    public,
    queues,
    resend,
    search,
    settings as settings_router,
    status_change_requests,
    tasks,
    templates,
    tracking,
    webhooks,
    websocket as ws_router,
    workflows,
)
from app.services import alert_service, metrics_service

# ============================================================================
# GCP Monitoring (Cloud Logging + Error Reporting)
# ============================================================================

apply_protobuf_json_depth_guard()

gcp_monitoring = setup_gcp_monitoring(settings.GCP_SERVICE_NAME)
if gcp_monitoring.logging_enabled:
    logging.info("GCP Cloud Logging: enabled")
if gcp_monitoring.error_reporter:
    logging.info("GCP Error Reporting: enabled")


def _get_org_id_for_alert(request: Request) -> UUID | None:
    session = getattr(request.state, "user_session", None)
    if session and getattr(session, "org_id", None):
        return session.org_id

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    try:
        from app.core.security import decode_session_token

        payload = decode_session_token(token)
        org_id = payload.get("org_id")
        return UUID(org_id) if org_id else None
    except Exception:
        return None


def _record_api_error_alert(
    request: Request,
    status_code: int,
    error_class: str | None = None,
) -> None:
    org_id = _get_org_id_for_alert(request)
    if not org_id:
        return

    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    request_id = request.headers.get("x-request-id")
    details = {
        "method": request.method,
        "path": route_path,
        "status_code": status_code,
    }
    if request_id:
        details["request_id"] = request_id

    db = SessionLocal()
    try:
        alert_service.create_or_update_alert(
            db=db,
            org_id=org_id,
            alert_type=AlertType.API_ERROR,
            severity=AlertSeverity.ERROR,
            title=f"API error {status_code}: {request.method} {route_path}",
            message="Unhandled server error",
            integration_key=route_path,
            error_class=error_class,
            http_status=status_code,
            details=details,
        )
    except Exception:
        logging.exception("Failed to record system alert for API error")
    finally:
        db.close()


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.websocket import (
        manager,
        start_session_revocation_listener,
        start_websocket_event_listener,
    )

    if settings.DB_MIGRATION_CHECK or settings.DB_AUTO_MIGRATE:
        status = db_migrations.ensure_migrations(engine, settings.DB_AUTO_MIGRATE)
        if not status.is_up_to_date and not settings.DB_AUTO_MIGRATE:
            logging.error(
                "Database migrations pending at startup: current=%s head=%s",
                status.current_heads,
                status.head_revisions,
            )

    manager.set_event_loop(asyncio.get_running_loop())
    await start_session_revocation_listener()
    await start_websocket_event_listener()
    yield


app = FastAPI(
    title="Surrogacy Force API",
    description="Multi-tenant Surrogacy Force case management API",
    version=settings.VERSION,
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
    lifespan=lifespan,
)

if settings.TRUST_PROXY_HEADERS:
    if ProxyHeadersMiddleware is None:
        logging.warning("ProxyHeadersMiddleware not available; TRUST_PROXY_HEADERS ignored")
    else:
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

configure_telemetry(app, engine)


# Report server errors to GCP Error Reporting when enabled.
@app.middleware("http")
async def gcp_error_reporting_middleware(request, call_next):
    try:
        response = await call_next(request)
        if response.status_code >= 500:
            _record_api_error_alert(
                request,
                response.status_code,
                error_class="http_response",
            )
        return response
    except HTTPException as exc:
        if exc.status_code >= 500:
            report_exception(gcp_monitoring.error_reporter, request)
            session = getattr(request.state, "user_session", None)
            context = build_log_context(
                user_id=str(session.user_id) if session else None,
                org_id=str(session.org_id) if session else None,
                request_id=request.headers.get("x-request-id"),
                route=request.url.path,
                method=request.method,
            )
            logging.exception("Unhandled HTTPException", extra=context)
            _record_api_error_alert(
                request,
                exc.status_code,
                error_class=exc.__class__.__name__,
            )
        raise
    except RateLimitExceeded:
        raise
    except Exception as exc:
        report_exception(gcp_monitoring.error_reporter, request)
        session = getattr(request.state, "user_session", None)
        context = build_log_context(
            user_id=str(session.user_id) if session else None,
            org_id=str(session.org_id) if session else None,
            request_id=request.headers.get("x-request-id"),
            route=request.url.path,
            method=request.method,
        )
        logging.exception("Unhandled exception", extra=context)
        _record_api_error_alert(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_class=exc.__class__.__name__,
        )
        raise


def _record_metrics(request: Request, status_code: int, duration_ms: int) -> None:
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    session = getattr(request.state, "user_session", None)
    org_id = session.org_id if session else None
    db = SessionLocal()
    try:
        metrics_service.record_request(
            db=db,
            route=route_path,
            method=request.method,
            status_code=status_code,
            duration_ms=duration_ms,
            org_id=org_id,
        )
    finally:
        db.close()


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = perf_counter()
    try:
        response = await call_next(request)
    except HTTPException as exc:
        duration_ms = int((perf_counter() - start) * 1000)
        _record_metrics(request, exc.status_code, duration_ms)
        raise
    except RateLimitExceeded:
        duration_ms = int((perf_counter() - start) * 1000)
        _record_metrics(request, status.HTTP_429_TOO_MANY_REQUESTS, duration_ms)
        raise
    except Exception:
        duration_ms = int((perf_counter() - start) * 1000)
        _record_metrics(request, status.HTTP_500_INTERNAL_SERVER_ERROR, duration_ms)
        raise

    duration_ms = int((perf_counter() - start) * 1000)
    _record_metrics(request, response.status_code, duration_ms)
    return response


# Enforce CSRF on state-changing requests when session cookie is present.
@app.middleware("http")
async def csrf_protection_middleware(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        # Skip CSRF for dev endpoints (protected by X-Dev-Secret instead)
        if request.url.path.startswith("/dev/"):
            pass
        elif request.cookies.get(COOKIE_NAME):
            if not validate_csrf(request):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Missing or invalid CSRF token. "
                            f"Include '{CSRF_HEADER}' header matching '{CSRF_COOKIE_NAME}' cookie."
                        )
                    },
                )
    response = await call_next(request)
    if request.cookies.get(COOKIE_NAME) and not request.cookies.get(CSRF_COOKIE_NAME):
        set_csrf_cookie(response)
    return response


# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - must be added before routers
# Tightened for production, but allow tenant subdomains.
tenant_origin_regex = None
if settings.PLATFORM_BASE_DOMAIN:
    scheme = "https?" if settings.is_dev else "https"
    tenant_origin_regex = rf"^{scheme}://([a-z0-9-]+\.)?{re.escape(settings.PLATFORM_BASE_DOMAIN)}$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=tenant_origin_regex,
    allow_credentials=True,  # Required for cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", CSRF_HEADER, "X-Dev-Secret"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)


# Security headers middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Protect against clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # Mitigate Spectre vulnerabilities
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    # Avoid caching API responses unless explicitly set by a handler.
    if "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


# ============================================================================
# Routers
# ============================================================================

# Auth router (always mounted)
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# OIDC discovery for Workload Identity Federation
app.include_router(oidc.router)

# Public endpoints (no auth required - for frontend middleware)
app.include_router(public.router)

# NOTE: Import routers MUST be registered BEFORE surrogates router
# to avoid /{surrogate_id} matching "/import" path segments
app.include_router(surrogates_import.router)  # /surrogates/import prefix
app.include_router(import_templates.router)
app.include_router(custom_fields.router)

# Surrogates module routers
app.include_router(surrogates.router, prefix="/surrogates", tags=["surrogates"])
app.include_router(
    notes.router, tags=["notes"]
)  # Mixed paths: /surrogates/{id}/notes and /notes/{id}
app.include_router(
    interviews.router, tags=["interviews"]
)  # Mixed paths: /surrogates/{id}/interviews and /interviews/{id}
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

# Surrogate Journey (timeline view)
app.include_router(journey.router)  # Authenticated journey endpoints
app.include_router(journey.export_router)  # Token-auth export view

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
app.include_router(monitoring.router)

# Analytics endpoints (admin dashboards)
app.include_router(analytics.router)

# Ops endpoints (integration health, alerts)
app.include_router(ops.router)

# Platform admin endpoints (ops console - cross-org)
app.include_router(platform.router, prefix="/platform", tags=["platform"])

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

# Application Forms
app.include_router(forms.router)
app.include_router(forms_public.router)

# Profile Card (case_manager+ only)
app.include_router(profile.router)

app.include_router(admin_meta.router)  # Already has prefix in router definition
app.include_router(admin_meta.ad_account_router)  # Meta ad account management
app.include_router(admin_meta.sync_router)  # Meta sync triggers

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

# Queue Management (Surrogate Routing)
app.include_router(queues.router, prefix="/queues", tags=["queues"])

# File Attachments
app.include_router(attachments.router, tags=["attachments"])

# Team Invitations
app.include_router(invites.router, tags=["invites"])

# Settings (organization and user preferences)
app.include_router(settings_router.router, tags=["settings"])

# Resend Email Configuration (Admin)
app.include_router(resend.router)

# Appointments (internal, authenticated)
app.include_router(appointments.router, prefix="/appointments", tags=["appointments"])

# Public Booking (unauthenticated)
app.include_router(booking.router, prefix="/book", tags=["booking"])

# Email Tracking (public endpoints for pixel/click tracking)
app.include_router(tracking.router)

# MFA (Multi-Factor Authentication)
app.include_router(mfa.router, prefix="/mfa", tags=["mfa"])

# Global Search
app.include_router(search.router)

# Status Change Requests (Admin approval workflow)
app.include_router(status_change_requests.router)

# Dev router (ONLY mounted in dev-like environments)
if settings.is_dev:
    app.include_router(dev.router, prefix="/dev", tags=["dev"])


# ============================================================================
# Health Checks
# ============================================================================

logger = logging.getLogger(__name__)


@app.get("/")
@limiter.exempt
def root():
    """Basic availability endpoint (scanner-friendly)."""
    return JSONResponse(
        content={"status": "ok"},
        headers={"Cache-Control": "public, max-age=3600", "Pragma": "public"},
    )


@app.get("/sitemap.xml")
@limiter.exempt
def sitemap():
    """Minimal sitemap to keep scanners happy."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url><loc>/</loc></url>\n"
        "</urlset>\n"
    )
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600", "Pragma": "public"},
    )


def _check_db_connection() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Readiness DB check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc


def _check_db_migrations() -> db_migrations.MigrationStatus | None:
    if not settings.DB_MIGRATION_CHECK:
        return None
    try:
        migration_status = db_migrations.get_migration_status(engine)
    except Exception as exc:
        logger.warning("Readiness migration check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database migration check failed",
        ) from exc
    if not migration_status.is_up_to_date:
        logger.error(
            "Database migrations pending: current=%s head=%s",
            migration_status.current_heads,
            migration_status.head_revisions,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database migrations pending",
        )
    return migration_status


def _check_redis_connection() -> None:
    try:
        client = get_sync_redis_client()
        if client is None:
            return
        client.ping()
    except Exception as exc:
        logger.warning("Readiness Redis check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis unavailable",
        ) from exc


@app.get("/healthz")
@limiter.exempt
def healthz():
    """Liveness probe (no external dependencies)."""
    return {"status": "ok"}


@app.get("/readyz")
@limiter.exempt
def readyz():
    """Readiness probe (checks database connectivity)."""
    _check_db_connection()
    migration_status = _check_db_migrations()
    _check_redis_connection()
    response = {"status": "ok", "env": settings.ENV, "version": settings.VERSION}
    if settings.DB_MIGRATION_CHECK:
        response["db_migrations"] = {
            "status": "ok",
            "current_heads": list(migration_status.current_heads) if migration_status else [],
            "head_revisions": list(migration_status.head_revisions) if migration_status else [],
        }
    else:
        response["db_migrations"] = {"status": "skipped"}
    return response


@app.get("/health/live")
@limiter.exempt
def health_live():
    """Liveness alias."""
    return healthz()


@app.get("/health/ready")
@limiter.exempt
def health_ready():
    """Readiness alias."""
    return readyz()


@app.get("/health")
@limiter.exempt
def health():
    """Legacy health endpoint (alias to readiness check)."""
    return readyz()
