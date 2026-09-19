"""Lifecycle operations for short-lived ops CLI credentials."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import OpsCliToken, User
from app.db.models.ops_cli import OpsCliLogin
from app.services.platform_service import log_admin_action

TOKEN_LIFETIME = timedelta(hours=8)
TOKEN_PREFIX = "sf_ops_"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_token(
    db: Session, user: User, request: Request | None = None, *, commit: bool = True
) -> tuple[OpsCliToken, str]:
    plaintext = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    credential = OpsCliToken(
        user_id=user.id,
        token_hash=hash_token(plaintext),
        token_version=user.token_version,
        environment=settings.ENV.lower(),
        expires_at=datetime.now(UTC) + TOKEN_LIFETIME,
    )
    db.add(credential)
    db.flush()
    log_admin_action(
        db,
        user.id,
        "ops_cli_token.created",
        metadata={"token_id": str(credential.id)},
        request=request,
    )
    if commit:
        db.commit()
        db.refresh(credential)
    return credential, plaintext


def list_tokens(db: Session, user_id: UUID) -> list[OpsCliToken]:
    return (
        db.query(OpsCliToken)
        .filter(OpsCliToken.user_id == user_id)
        .order_by(OpsCliToken.created_at.desc())
        .all()
    )


def start_login(db: Session) -> dict:
    now = datetime.now(UTC)
    db.query(OpsCliLogin).filter(OpsCliLogin.expires_at <= now).delete()
    device_code = secrets.token_urlsafe(32)
    code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(12))
    db.add(
        OpsCliLogin(
            device_hash=hash_token(device_code),
            code_hash=hash_token(code),
            environment=settings.ENV.lower(),
            expires_at=now + timedelta(minutes=10),
        )
    )
    db.commit()
    return {
        "device_code": device_code,
        "user_code": "-".join(code[i : i + 4] for i in range(0, 12, 4)),
        "expires_in": 600,
        "interval": 3,
    }


def _valid_login(grant: OpsCliLogin | None) -> bool:
    return bool(
        grant
        and grant.expires_at > datetime.now(UTC)
        and grant.environment == settings.ENV.lower()
        and grant.consumed_at is None
    )


def approve_login(db: Session, user: User, code: str, request: Request) -> bool:
    normalized = code.upper().replace("-", "").replace(" ", "")
    grant = (
        db.query(OpsCliLogin)
        .filter(OpsCliLogin.code_hash == hash_token(normalized))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not _valid_login(grant) or grant.user_id is not None:
        return False
    grant.user_id = user.id
    grant.token_version = user.token_version
    log_admin_action(db, user.id, "ops_cli_login.approved", request=request)
    db.commit()
    return True


def exchange_login(db: Session, device_code: str, request: Request) -> dict:
    grant = (
        db.query(OpsCliLogin)
        .filter(OpsCliLogin.device_hash == hash_token(device_code))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if not _valid_login(grant):
        return {"status": "expired"}
    if grant.user_id is None:
        return {"status": "pending"}
    user = db.query(User).filter(User.id == grant.user_id).one()
    allowlisted = user.email.lower() in settings.platform_admin_emails_list
    is_admin = (
        user.is_platform_admin and allowlisted
        if settings.is_prod
        else user.is_platform_admin or allowlisted
    )
    if not user.is_active or not is_admin or user.token_version != grant.token_version:
        return {"status": "expired"}
    grant.consumed_at = datetime.now(UTC)
    credential, plaintext = mint_token(db, user, request, commit=False)
    db.commit()
    return {"status": "approved", "token": plaintext, "expires_at": credential.expires_at}


def revoke_token(
    db: Session, user_id: UUID, token_id: UUID, request: Request | None = None
) -> bool:
    credential = (
        db.query(OpsCliToken)
        .filter(OpsCliToken.id == token_id, OpsCliToken.user_id == user_id)
        .first()
    )
    if not credential:
        return False
    if credential.revoked_at is None:
        credential.revoked_at = datetime.now(UTC)
        log_admin_action(
            db,
            user_id,
            "ops_cli_token.revoked",
            metadata={"token_id": str(token_id)},
            request=request,
        )
        db.commit()
    return True
