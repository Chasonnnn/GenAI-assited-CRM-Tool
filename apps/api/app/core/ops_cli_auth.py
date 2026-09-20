"""Narrow bearer authentication for explicitly opted-in ops CLI routes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.db.models import OpsCliToken, User
from app.services.ops_cli_service import TOKEN_PREFIX, hash_token


@dataclass(frozen=True)
class OpsCliContext:
    user_id: UUID
    token_id: UUID
    expires_at: datetime


def require_ops_cli(request: Request, db: Session = Depends(get_db)) -> OpsCliContext:
    if settings.ENV.lower() not in ("dev", "development", "test") and request.url.scheme != "https":
        raise HTTPException(status_code=400, detail="TLS is required")

    authorization = request.headers.get("authorization", "")
    scheme, _, plaintext = authorization.partition(" ")
    if scheme.lower() != "bearer" or not plaintext.startswith(TOKEN_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid CLI credential")

    now = datetime.now(UTC)
    row = (
        db.query(OpsCliToken, User)
        .join(User, User.id == OpsCliToken.user_id)
        .filter(OpsCliToken.token_hash == hash_token(plaintext))
        .first()
    )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid CLI credential")
    token, user = row
    in_allowlist = user.email.lower() in settings.platform_admin_emails_list
    is_admin = (
        user.is_platform_admin and in_allowlist
        if settings.is_prod
        else user.is_platform_admin or in_allowlist
    )
    if (
        token.revoked_at is not None
        or token.expires_at <= now
        or token.environment != settings.ENV.lower()
        or token.token_version != user.token_version
        or not user.is_active
        or not is_admin
    ):
        raise HTTPException(status_code=401, detail="CLI credential is no longer valid")
    return OpsCliContext(user_id=user.id, token_id=token.id, expires_at=token.expires_at)
