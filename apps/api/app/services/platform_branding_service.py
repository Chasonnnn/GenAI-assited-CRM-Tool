"""Platform branding service (logo, etc.)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import PlatformBranding


def get_branding(db: Session) -> PlatformBranding:
    branding = db.query(PlatformBranding).first()
    if branding:
        return branding
    branding = PlatformBranding()
    db.add(branding)
    db.flush()
    return branding


def update_branding(db: Session, *, logo_url: str | None) -> PlatformBranding:
    branding = get_branding(db)
    branding.logo_url = logo_url
    db.flush()
    return branding
