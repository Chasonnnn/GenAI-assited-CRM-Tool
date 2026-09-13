"""Manual template sends retain the sender's live authority through delivery."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.db.models import (
    EmailTemplate,
    Membership,
    Organization,
    ResendSettings,
    RolePermission,
    User,
)
from app.services import email_delivery_dispatch, resend_settings_service
from app.services.email_delivery_service import (
    DeliveryLeaseLost,
    DeliveryRoute,
    EmailDeliveryConflict,
    EmailSource,
    RenderedEmail,
    claim_due_deliveries,
    queue_rendered_email,
)
from app.services.resend_transport import ResendSendResult
from tests.test_record_scopes_v2 import _record
from tests.test_record_scopes_v2 import context as context


@pytest.fixture
def delivery_context(db, context, monkeypatch):
    record = _record(db, context.intake, "surrogate")
    template = EmailTemplate(
        organization_id=context.org.id,
        name="Personal message",
        subject="Hello",
        body="<p>Hello</p>",
        scope="personal",
        owner_user_id=context.intake.user_id,
        created_by_user_id=context.intake.user_id,
        is_active=True,
    )
    db.add(template)
    db.add(
        ResendSettings(
            organization_id=context.org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_secret"),
            from_email="care@example.com",
            webhook_id=str(uuid4()),
        )
    )
    db.flush()
    transport = AsyncMock(
        return_value=ResendSendResult(
            success=True, message_id="test-provider-message", status_code=200
        )
    )
    monkeypatch.setattr(email_delivery_dispatch.resend_transport, "send_email", transport)
    monkeypatch.setattr(
        email_delivery_dispatch.email_provider_admission_service,
        "reserve_provider_request_slot",
        lambda *args, **kwargs: SimpleNamespace(send_at=datetime.now(UTC)),
    )
    return SimpleNamespace(**vars(context), record=record, template=template, transport=transport)


def _queue(db, ctx, *, source_type="manual_template_email", actor_id=None, key=None):
    return queue_rendered_email(
        db,
        organization_id=ctx.org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{ctx.org.id}",
        rendered_email=RenderedEmail(
            recipient_email=ctx.record.email,
            subject="Hello",
            html="<p>Hello</p>",
            text="Hello",
            from_email="care@example.com",
        ),
        source=EmailSource(
            source_type=source_type,
            actor_user_id=actor_id or ctx.intake.user_id,
            template_id=ctx.template.id,
            surrogate_id=ctx.record.id,
        ),
        idempotency_key=key or f"manual-template/{uuid4()}",
        schedule_at=datetime.now(UTC) - timedelta(seconds=1),
        commit=False,
    )


def _claim(db):
    return claim_due_deliveries(
        db, worker_id="manual-template-test", limit=1, lease_for=timedelta(minutes=2)
    )[0]


def _revoke(db, ctx, reason):
    if reason == "permission":
        db.add(
            RolePermission(
                organization_id=ctx.org.id,
                role="intake_specialist",
                permission="send_email",
                is_granted=False,
            )
        )
    elif reason == "membership":
        db.query(Membership).filter_by(
            organization_id=ctx.org.id, user_id=ctx.intake.user_id
        ).one().is_active = False
    elif reason == "user":
        db.get(User, ctx.intake.user_id).is_active = False
    elif reason == "role":
        db.query(Membership).filter_by(
            organization_id=ctx.org.id, user_id=ctx.intake.user_id
        ).one().role = "operations"
    elif reason == "record_scope":
        ctx.record.owner_id = ctx.manager.user_id
    elif reason == "template_owner":
        ctx.template.owner_user_id = ctx.manager.user_id
    elif reason == "template_inactive":
        ctx.template.is_active = False
    elif reason in {"template_org", "record_org"}:
        other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
        db.add(other)
        db.flush()
        (ctx.template if reason == "template_org" else ctx.record).organization_id = other.id
    elif reason == "actor_org":
        other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
        db.add(other)
        db.flush()
        db.query(Membership).filter_by(
            organization_id=ctx.org.id, user_id=ctx.intake.user_id
        ).one().organization_id = other.id
    db.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    [
        "permission",
        "membership",
        "user",
        "role",
        "record_scope",
        "template_owner",
        "template_inactive",
        "template_org",
        "record_org",
        "actor_org",
    ],
)
async def test_manual_template_delivery_rechecks_authority(db, delivery_context, reason):
    ctx = delivery_context
    queued = _queue(db, ctx)
    claim = _claim(db)
    _revoke(db, ctx, reason)
    result = await email_delivery_dispatch.dispatch_claim(db, claim=claim)
    ctx.transport.assert_not_awaited()
    assert result.status == "cancelled"
    assert result.last_error_type == "manual_template_authority_revoked"
    assert queued.email_log.status == "skipped"


@pytest.mark.asyncio
async def test_manual_template_delivery_checks_again_after_provider_admission(
    db, delivery_context, monkeypatch
):
    ctx = delivery_context
    _queue(db, ctx)
    claim = _claim(db)

    def reserve(*args, **kwargs):
        _revoke(db, ctx, "record_scope")
        return SimpleNamespace(send_at=datetime.now(UTC))

    monkeypatch.setattr(
        email_delivery_dispatch.email_provider_admission_service,
        "reserve_provider_request_slot",
        reserve,
    )
    result = await email_delivery_dispatch.dispatch_claim(db, claim=claim)
    assert result.status == "cancelled"
    ctx.transport.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_manual_template_delivery_is_idempotent(db, delivery_context):
    ctx = delivery_context
    first = _queue(db, ctx)
    duplicate = _queue(db, ctx, key=first.delivery.idempotency_key)
    assert duplicate.delivery.id == first.delivery.id
    claim = _claim(db)
    result = await email_delivery_dispatch.dispatch_claim(db, claim=claim)
    assert result.status == "sent"
    ctx.transport.assert_awaited_once()
    with pytest.raises(DeliveryLeaseLost):
        await email_delivery_dispatch.dispatch_claim(db, claim=claim)
    ctx.transport.assert_awaited_once()


@pytest.mark.asyncio
async def test_another_actor_cannot_reuse_manual_template_idempotency_key(db, delivery_context):
    ctx = delivery_context
    first = _queue(db, ctx)
    with pytest.raises(EmailDeliveryConflict):
        _queue(db, ctx, key=first.delivery.idempotency_key, actor_id=ctx.manager.user_id)


@pytest.mark.asyncio
async def test_legacy_manual_template_delivery_preserves_queued_semantics(db, delivery_context):
    from app.db.models import OrganizationPermissionPolicy

    ctx = delivery_context
    db.query(OrganizationPermissionPolicy).filter_by(organization_id=ctx.org.id).delete()
    _queue(db, ctx)
    claim = _claim(db)
    _revoke(db, ctx, "membership")
    result = await email_delivery_dispatch.dispatch_claim(db, claim=claim)
    assert result.status == "sent"
    ctx.transport.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoked_retry_preserves_unknown_provider_outcome(db, delivery_context):
    ctx = delivery_context
    queued = _queue(db, ctx)
    ctx.transport.side_effect = TimeoutError("Synthetic provider timeout")
    result = await email_delivery_dispatch.dispatch_claim(db, claim=_claim(db))
    assert result.status == "retry_scheduled"
    result.run_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    _revoke(db, ctx, "permission")
    result = await email_delivery_dispatch.dispatch_claim(db, claim=_claim(db))
    assert result.status == "reconciliation_required"
    assert result.last_error_type == "manual_template_authority_revoked"
    assert queued.email_log.status == "pending"
    ctx.transport.assert_awaited_once()
