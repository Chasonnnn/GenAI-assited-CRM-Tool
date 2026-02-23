"""Mailbox source administration and sync control APIs."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.security import (
    create_oauth_state_payload,
    generate_oauth_nonce,
    generate_oauth_state,
    parse_oauth_state_payload,
    verify_oauth_state,
    verify_secret,
)
from app.db.enums import AuditEventType
from app.db.session import SessionLocal
from app.schemas.auth import UserSession
from app.schemas.ticketing import (
    InternalGmailSyncScheduleResponse,
    MailboxJobEnqueueResponse,
    MailboxListResponse,
    MailboxPauseRequest,
    MailboxPauseResponse,
    MailboxRead,
    MailboxSyncStatusResponse,
    OAuthStartResponse,
)
from app.services import audit_service, oauth_service, org_service, ticketing_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/mailboxes",
    tags=["Mailboxes"],
    dependencies=[Depends(require_permission("manage_integrations"))],
)

_internal_router = APIRouter(prefix="/internal/scheduled", tags=["internal"])

OAUTH_STATE_MAX_AGE = 300
OAUTH_STATE_COOKIE_NAME = "journal_mailbox_oauth_state"
OAUTH_STATE_COOKIE_PATH = "/mailboxes"


def _journal_redirect_uri() -> str:
    base = settings.API_BASE_URL.rstrip("/")
    return f"{base}/mailboxes/journal/gmail/oauth/callback"


def _verify_internal_secret(x_internal_secret: str = Header(...)) -> None:
    expected = settings.INTERNAL_SECRET if hasattr(settings, "INTERNAL_SECRET") else None
    if not expected:
        raise HTTPException(status_code=501, detail="INTERNAL_SECRET not configured")
    if not verify_secret(x_internal_secret, expected):
        raise HTTPException(status_code=403, detail="Invalid internal secret")


@router.get("", response_model=MailboxListResponse)
def list_mailboxes(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MailboxListResponse:
    """List mailbox sources and sync state for the current org."""
    rows = ticketing_service.list_mailboxes(db, org_id=session.org_id)
    return MailboxListResponse(
        items=[
            MailboxRead(
                id=row.id,
                kind=row.kind.value if hasattr(row.kind, "value") else str(row.kind),
                provider=row.provider.value
                if hasattr(row.provider, "value")
                else str(row.provider),
                email_address=row.email_address,
                display_name=row.display_name,
                is_enabled=row.is_enabled,
                ingestion_paused_until=row.ingestion_paused_until,
                ingestion_pause_reason=row.ingestion_pause_reason,
                gmail_history_id=row.gmail_history_id,
                gmail_watch_expiration_at=row.gmail_watch_expiration_at,
                gmail_watch_last_renewed_at=row.gmail_watch_last_renewed_at,
                gmail_watch_topic_name=row.gmail_watch_topic_name,
                gmail_watch_last_error=row.gmail_watch_last_error,
                last_incremental_sync_at=row.last_incremental_sync_at,
                last_full_sync_at=row.last_full_sync_at,
                last_sync_error=row.last_sync_error,
                default_queue_id=row.default_queue_id,
                user_integration_id=row.user_integration_id,
                credential_id=row.credential_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
    )


@router.post(
    "/journal/gmail/oauth/start",
    response_model=OAuthStartResponse,
    dependencies=[Depends(require_csrf_header)],
)
def start_journal_oauth(
    request: Request,
    response: Response,
    _session: UserSession = Depends(get_current_session),
) -> OAuthStartResponse:
    """Start OAuth flow for organization journal mailbox."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    state = generate_oauth_state()
    nonce = generate_oauth_nonce()
    state_payload = create_oauth_state_payload(
        state,
        nonce,
        request.headers.get("user-agent", ""),
    )

    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=state_payload,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path=OAUTH_STATE_COOKIE_PATH,
    )

    auth_url = oauth_service.get_gmail_auth_url(_journal_redirect_uri(), state)
    return OAuthStartResponse(auth_url=auth_url)


@router.get("/journal/gmail/oauth/callback")
async def complete_journal_oauth(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> RedirectResponse:
    """Finish OAuth for journal mailbox and save org mailbox credential."""
    org = org_service.get_org_by_id(db, session.org_id)
    base_url = org_service.get_org_portal_base_url(org)

    error_response = RedirectResponse(
        f"{base_url}/settings/integrations?error=journal_oauth_state",
        status_code=302,
    )
    error_response.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=OAUTH_STATE_COOKIE_PATH)

    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE_NAME)
    if not state_cookie:
        return error_response

    try:
        stored_payload = parse_oauth_state_payload(state_cookie)
    except Exception:
        return error_response

    valid, _ = verify_oauth_state(
        stored_payload,
        state,
        request.headers.get("user-agent", ""),
    )
    if not valid:
        return error_response

    try:
        tokens = await oauth_service.exchange_gmail_code(code, _journal_redirect_uri())
        user_info = await oauth_service.get_gmail_user_info(tokens["access_token"])

        scopes = ticketing_service.parse_granted_scopes_from_tokens(tokens)

        mailbox = ticketing_service.create_or_update_journal_mailbox(
            db,
            org_id=session.org_id,
            account_email=user_info.get("email") or "",
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token") or "",
            expires_in=tokens.get("expires_in"),
            granted_scopes=scopes,
        )

        audit_service.log_event(
            db=db,
            org_id=session.org_id,
            event_type=AuditEventType.INTEGRATION_CONNECTED,
            actor_user_id=session.user_id,
            target_type="mailbox",
            target_id=mailbox.id,
            details={
                "integration_type": "journal_gmail",
                "account_email": audit_service.hash_email(user_info.get("email", "") or ""),
                "scopes": scopes or [],
            },
            request=request,
        )
        db.commit()

        success = RedirectResponse(
            f"{base_url}/settings/integrations?success=journal_gmail",
            status_code=302,
        )
        success.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=OAUTH_STATE_COOKIE_PATH)
        return success
    except Exception as exc:
        logger.exception("Journal mailbox OAuth callback failed: %s", exc)
        failure = RedirectResponse(
            f"{base_url}/settings/integrations?error=journal_oauth_failed",
            status_code=302,
        )
        failure.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=OAUTH_STATE_COOKIE_PATH)
        return failure


@router.post(
    "/{mailbox_id}/sync/backfill",
    response_model=MailboxJobEnqueueResponse,
    dependencies=[Depends(require_csrf_header)],
)
def enqueue_backfill(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MailboxJobEnqueueResponse:
    """Enqueue full historical backfill."""
    job_id = ticketing_service.enqueue_mailbox_backfill(
        db,
        org_id=session.org_id,
        mailbox_id=mailbox_id,
        reason="manual_backfill",
    )
    return MailboxJobEnqueueResponse(
        queued=job_id is not None,
        job_id=job_id,
        reason="duplicate" if job_id is None else None,
    )


@router.post(
    "/{mailbox_id}/sync/history",
    response_model=MailboxJobEnqueueResponse,
    dependencies=[Depends(require_csrf_header)],
)
def enqueue_history_sync(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MailboxJobEnqueueResponse:
    """Enqueue incremental history sync."""
    job_id = ticketing_service.enqueue_mailbox_history_sync(
        db,
        org_id=session.org_id,
        mailbox_id=mailbox_id,
        reason="manual_incremental",
    )
    return MailboxJobEnqueueResponse(
        queued=job_id is not None,
        job_id=job_id,
        reason="duplicate" if job_id is None else None,
    )


@router.get("/{mailbox_id}/sync/status", response_model=MailboxSyncStatusResponse)
def mailbox_sync_status(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MailboxSyncStatusResponse:
    """Get mailbox sync status and queue metrics."""
    status_view = ticketing_service.get_mailbox_sync_status(
        db,
        org_id=session.org_id,
        mailbox_id=mailbox_id,
    )
    return MailboxSyncStatusResponse(
        mailbox_id=status_view.mailbox_id,
        is_enabled=status_view.is_enabled,
        paused_until=status_view.paused_until,
        gmail_history_id=status_view.gmail_history_id,
        gmail_watch_expiration_at=status_view.gmail_watch_expiration_at,
        gmail_watch_last_renewed_at=status_view.gmail_watch_last_renewed_at,
        gmail_watch_topic_name=status_view.gmail_watch_topic_name,
        gmail_watch_last_error=status_view.gmail_watch_last_error,
        last_full_sync_at=status_view.last_full_sync_at,
        last_incremental_sync_at=status_view.last_incremental_sync_at,
        last_sync_error=status_view.last_sync_error,
        queued_jobs_by_type=status_view.queued_jobs_by_type,
        running_jobs_by_type=status_view.running_jobs_by_type,
    )


@router.post(
    "/{mailbox_id}/sync/pause",
    response_model=MailboxPauseResponse,
    dependencies=[Depends(require_csrf_header)],
)
def pause_mailbox(
    mailbox_id: UUID,
    data: MailboxPauseRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MailboxPauseResponse:
    """Pause mailbox ingestion."""
    paused_until, pause_reason = ticketing_service.pause_mailbox_ingestion(
        db,
        org_id=session.org_id,
        mailbox_id=mailbox_id,
        minutes=data.minutes,
        reason=data.reason,
    )
    return MailboxPauseResponse(
        mailbox_id=mailbox_id,
        paused=True,
        paused_until=paused_until,
        pause_reason=pause_reason,
    )


@router.post(
    "/{mailbox_id}/sync/resume",
    response_model=MailboxJobEnqueueResponse,
    dependencies=[Depends(require_csrf_header)],
)
def resume_mailbox(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MailboxJobEnqueueResponse:
    """Resume mailbox ingestion and queue incremental sync."""
    job_id = ticketing_service.resume_mailbox_ingestion(
        db,
        org_id=session.org_id,
        mailbox_id=mailbox_id,
    )
    return MailboxJobEnqueueResponse(
        queued=job_id is not None,
        job_id=job_id,
        reason="duplicate" if job_id is None else None,
    )


@_internal_router.post("/gmail-sync", response_model=InternalGmailSyncScheduleResponse)
def schedule_gmail_sync_jobs(
    x_internal_secret: str = Header(...),
) -> InternalGmailSyncScheduleResponse:
    """Cron/fallback trigger to enqueue incremental Gmail sync jobs."""
    _verify_internal_secret(x_internal_secret)

    with SessionLocal() as db:
        counts = ticketing_service.schedule_incremental_sync_jobs(db)

    return InternalGmailSyncScheduleResponse(**counts)


internal_router = _internal_router
