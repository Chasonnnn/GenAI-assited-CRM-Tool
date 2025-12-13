"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.routers import auth, cases, notes, tasks, webhooks

app = FastAPI(
    title="CRM API",
    description="Multi-tenant CRM and case management API",
    version="0.2.0",
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

# Webhooks router (external integrations)
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

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