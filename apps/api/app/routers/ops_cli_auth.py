"""Browser-approved login and self-service CLI sessions."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import PlatformUserSession, get_db, require_csrf_header, require_platform_admin
from app.core.ops_cli_auth import OpsCliContext, require_ops_cli
from app.core.rate_limit import limiter
from app.services import ops_cli_service, user_service

router = APIRouter(prefix="/platform/cli", tags=["platform-cli"])


class TokenSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None


class LoginApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=12, max_length=32, pattern=r"^[a-zA-Z0-9 -]+$")


class LoginExchange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_code: str = Field(min_length=40, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


def require_tls(request: Request) -> None:
    if settings.ENV.lower() not in ("dev", "development", "test") and request.url.scheme != "https":
        raise HTTPException(status_code=400, detail="TLS is required")


def require_verified_ops_admin(
    session: Annotated[PlatformUserSession, Depends(require_platform_admin)],
) -> PlatformUserSession:
    """Require an explicitly MFA-verified cookie session for credential management."""
    if not session.mfa_verified:
        raise HTTPException(status_code=403, detail="MFA verification required")
    return session


@router.post("/login/start", dependencies=[Depends(require_tls)])
@limiter.limit("10/minute")
def start_login(
    request: Request, response: Response, db: Annotated[Session, Depends(get_db)]
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return ops_cli_service.start_login(db)


@router.post("/login/exchange", dependencies=[Depends(require_tls)])
@limiter.limit("60/minute")
def exchange_login(
    body: LoginExchange,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return ops_cli_service.exchange_login(db, body.device_code, request)


@router.post("/login/approve", dependencies=[Depends(require_csrf_header)])
@limiter.limit("10/minute")
def approve_login(
    body: LoginApproval,
    request: Request,
    response: Response,
    session: Annotated[PlatformUserSession, Depends(require_verified_ops_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    user = user_service.get_user_by_id(db, session.user_id)
    if not ops_cli_service.approve_login(db, user, body.code, request):
        raise HTTPException(
            status_code=400, detail="Login code is invalid, expired, or already used"
        )
    return {"approved": True}


@router.get("/tokens", response_model=list[TokenSummary])
def list_tokens(
    session: Annotated[PlatformUserSession, Depends(require_verified_ops_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TokenSummary]:
    return [
        TokenSummary.model_validate(item)
        for item in ops_cli_service.list_tokens(db, session.user_id)
    ]


@router.delete(
    "/tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def revoke_token(
    token_id: UUID,
    request: Request,
    session: Annotated[PlatformUserSession, Depends(require_verified_ops_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    if not ops_cli_service.revoke_token(db, session.user_id, token_id, request):
        raise HTTPException(status_code=404, detail="CLI credential not found")


@router.get("/whoami")
def whoami(
    context: Annotated[OpsCliContext, Depends(require_ops_cli)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user = user_service.get_user_by_id(db, context.user_id)
    return {"user_id": user.id, "email": user.email, "expires_at": context.expires_at}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    context: Annotated[OpsCliContext, Depends(require_ops_cli)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    ops_cli_service.revoke_token(db, context.user_id, context.token_id, request)
