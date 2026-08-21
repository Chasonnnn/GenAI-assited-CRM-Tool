from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User, UserPermissionOverride
from app.main import app
from app.services import session_service


@asynccontextmanager
async def _messaging_client_with_email_permission(db, organization_id):
    user = User(
        id=uuid4(),
        email=f"messaging-campaign-{uuid4().hex[:8]}@test.com",
        display_name="Messaging Campaign Operator",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add_all(
        [
            Membership(
                id=uuid4(),
                user_id=user.id,
                organization_id=organization_id,
                role=Role.CASE_MANAGER.value,
            ),
            UserPermissionOverride(
                id=uuid4(),
                organization_id=organization_id,
                user_id=user.id,
                permission="manage_email_templates",
                override_type="grant",
            ),
        ]
    )
    db.flush()
    token = create_session_token(
        user_id=user.id,
        org_id=organization_id,
        role=Role.CASE_MANAGER.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=organization_id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    csrf_token = generate_csrf_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    ) as client:
        yield client
    app.dependency_overrides.clear()


def _published_message_template(db, test_org, test_user, *, purpose: str, body: str):
    from app.db.models import MessageTemplate

    template = MessageTemplate(
        organization_id=test_org.id,
        template_key=uuid4(),
        version=1,
        name=f"{purpose.title()} v1",
        purpose=purpose,
        body=body,
        content_hash=hashlib.sha256(body.encode()).hexdigest(),
        status="published",
        published_at=datetime.now(UTC),
        created_by_user_id=test_user.id,
    )
    db.add(template)
    db.flush()
    return template


def _messaging_surrogate(db, test_org, test_user, default_stage):
    from app.core.encryption import hash_email, hash_phone
    from app.db.models import Surrogate

    phone = "+14155550185"
    surrogate = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Message Recipient",
        email="message-recipient@example.com",
        email_hash=hash_email("message-recipient@example.com"),
        phone=phone,
        phone_hash=hash_phone(phone),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _consent_for_surrogate(db, test_org, surrogate, *, purpose: str):
    from app.services import messaging_consent_service

    return messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=surrogate.phone,
        purpose=purpose,
        affirmative=True,
        disclosure_text=f"{purpose.title()} disclosure",
        source="website",
        source_reference=f"{surrogate.id}-{purpose}",
        occurred_at=datetime.now(UTC),
        idempotency_key=f"{surrogate.id}-{purpose}",
        evidence_metadata={"affirmative_action": "checked"},
        surrogate_id=surrogate.id,
    )


def test_messaging_campaign_contract_requires_promotional_template_and_no_unsubscribe_bypass():
    from app.schemas.campaign import CampaignCreate

    with pytest.raises(ValidationError, match="include_unsubscribed"):
        CampaignCreate(
            name="Invalid SMS campaign",
            channel="messaging",
            message_template_version_id=uuid4(),
            recipient_type="case",
            include_unsubscribed=True,
        )


def test_messaging_campaign_materializes_promotional_outbox_occurrence(
    db,
    test_org,
    test_user,
    default_stage,
):
    from app.db.models import CampaignRecipient, MessageDelivery
    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service

    body = "EWI Surrogacy opportunities. Msg & data rates may apply. HELP. Reply STOP to opt out."
    template = _published_message_template(
        db,
        test_org,
        test_user,
        purpose="promotional",
        body=body,
    )
    template.is_enrollment_confirmation = True
    surrogate = _messaging_surrogate(db, test_org, test_user, default_stage)
    consent = _consent_for_surrogate(db, test_org, surrogate, purpose="promotional")
    campaign = campaign_service.create_campaign(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=CampaignCreate(
            name="Promotional SMS campaign",
            channel="messaging",
            message_template_version_id=template.id,
            recipient_type="case",
        ),
    )
    db.commit()

    _message, run_id, _scheduled_at = campaign_service.enqueue_campaign_send(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        user_id=test_user.id,
        send_now=True,
    )
    assert run_id is not None
    campaign_service.execute_campaign_run(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run_id,
        actor_user_id=test_user.id,
    )

    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.run_id == run_id).one()
    delivery = (
        db.query(MessageDelivery)
        .filter(
            MessageDelivery.organization_id == test_org.id,
            MessageDelivery.id == recipient.message_delivery_id,
        )
        .one()
    )
    assert recipient.recipient_email is None
    assert recipient.recipient_phone_last4 == "0185"
    assert delivery.contact_id == consent.contact_id
    assert delivery.purpose == "promotional"
    assert delivery.route_id is not None
    assert delivery.template_version_id == template.id
    assert delivery.idempotency_key == f"campaign-message/{recipient.id}/v0"


def test_messaging_campaign_rejects_stale_contact_after_entity_phone_changes(
    db,
    test_org,
    test_user,
    default_stage,
):
    from app.core.encryption import hash_phone
    from app.db.models import CampaignRecipient, MessageDelivery
    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service

    template = _published_message_template(
        db,
        test_org,
        test_user,
        purpose="promotional",
        body="EWI Surrogacy opportunities. Reply STOP to opt out.",
    )
    template.is_enrollment_confirmation = True
    surrogate = _messaging_surrogate(db, test_org, test_user, default_stage)
    _consent_for_surrogate(db, test_org, surrogate, purpose="promotional")
    surrogate.phone = "+14155550186"
    surrogate.phone_hash = hash_phone(surrogate.phone)
    campaign = campaign_service.create_campaign(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=CampaignCreate(
            name="Stale contact guard",
            channel="messaging",
            message_template_version_id=template.id,
            recipient_type="case",
        ),
    )
    db.commit()

    _message, run_id, _scheduled_at = campaign_service.enqueue_campaign_send(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        user_id=test_user.id,
        send_now=True,
    )
    campaign_service.execute_campaign_run(
        db,
        org_id=test_org.id,
        campaign_id=campaign.id,
        run_id=run_id,
        actor_user_id=test_user.id,
    )

    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.run_id == run_id).one()
    assert recipient.status == "skipped"
    assert recipient.skip_reason == "consent_unknown"
    assert (
        db.query(MessageDelivery).filter(MessageDelivery.organization_id == test_org.id).count()
        == 0
    )


async def test_messaging_campaign_retry_stays_in_durable_outbox(
    authed_client,
    db,
    test_org,
    test_user,
):
    from app.db.enums import JobType
    from app.db.models import CampaignRecipient, CampaignRun, Job
    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service

    template = _published_message_template(
        db,
        test_org,
        test_user,
        purpose="promotional",
        body="EWI Surrogacy promotional texts. Reply STOP to opt out.",
    )
    campaign = campaign_service.create_campaign(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=CampaignCreate(
            name="Messaging retry boundary",
            channel="messaging",
            message_template_version_id=template.id,
            recipient_type="case",
        ),
    )
    campaign.status = "failed"
    run = CampaignRun(
        organization_id=test_org.id,
        campaign_id=campaign.id,
        status="failed",
        total_count=1,
        failed_count=1,
    )
    db.add(run)
    db.flush()
    db.add(
        CampaignRecipient(
            run_id=run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_phone_last4="0185",
            status="failed",
            error="Simulated provider failure",
        )
    )
    db.commit()
    jobs_before = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.CAMPAIGN_SEND.value,
        )
        .count()
    )

    response = await authed_client.post(f"/campaigns/{campaign.id}/runs/{run.id}/retry-failed")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Messaging delivery retries are managed by the durable messaging outbox"
    )
    db.refresh(campaign)
    db.refresh(run)
    assert campaign.status == "failed"
    assert run.status == "failed"
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.CAMPAIGN_SEND.value,
        )
        .count()
        == jobs_before
    )


async def test_messaging_campaign_delete_requires_messaging_operator(
    db,
    test_org,
    test_user,
):
    from app.schemas.campaign import CampaignCreate
    from app.services import campaign_service

    template = _published_message_template(
        db,
        test_org,
        test_user,
        purpose="promotional",
        body="EWI Surrogacy promotional texts. Reply STOP to opt out.",
    )
    campaign = campaign_service.create_campaign(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=CampaignCreate(
            name="Protected messaging draft",
            channel="messaging",
            message_template_version_id=template.id,
            recipient_type="case",
        ),
    )
    db.commit()

    async with _messaging_client_with_email_permission(db, test_org.id) as client:
        response = await client.delete(f"/campaigns/{campaign.id}")

    assert response.status_code == 403
    assert campaign_service.get_campaign(db, test_org.id, campaign.id) is not None


def test_send_message_workflow_requires_published_purpose_matching_template(
    db,
    test_org,
    test_user,
):
    from app.db.enums import WorkflowTriggerType
    from app.schemas.workflow import WorkflowCreate
    from app.services import workflow_service

    template = _published_message_template(
        db,
        test_org,
        test_user,
        purpose="operational",
        body="Operational update",
    )

    with pytest.raises(ValueError, match="purpose"):
        workflow_service.create_workflow(
            db,
            test_org.id,
            test_user.id,
            WorkflowCreate(
                name="Wrong purpose",
                scope="org",
                trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
                actions=[
                    {
                        "action_type": "send_message",
                        "purpose": "promotional",
                        "message_template_version_id": str(template.id),
                    }
                ],
            ),
        )


def test_send_message_workflow_materializes_deterministic_outbox_without_inline_transport(
    db,
    test_org,
    test_user,
    default_stage,
    monkeypatch,
):
    from app.db.models import MessageDelivery
    from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter

    body = "EWI Surrogacy operational updates. Msg & data rates may apply. HELP. Reply STOP to opt out."
    template = _published_message_template(
        db,
        test_org,
        test_user,
        purpose="operational",
        body=body,
    )
    template.is_enrollment_confirmation = True
    surrogate = _messaging_surrogate(db, test_org, test_user, default_stage)
    _consent_for_surrogate(db, test_org, surrogate, purpose="operational")

    def _forbid_inline_send(*_args, **_kwargs):
        pytest.fail("workflow actions must materialize an outbox row, not call Twilio")

    monkeypatch.setattr(
        "app.services.twilio_transport.send_message",
        _forbid_inline_send,
    )
    execution_id = uuid4()
    adapter = DefaultWorkflowDomainAdapter()
    first = adapter.execute_action(
        db=db,
        action={
            "action_type": "send_message",
            "purpose": "operational",
            "message_template_version_id": str(template.id),
        },
        entity=surrogate,
        entity_type="surrogate",
        event_id=uuid4(),
        depth=0,
        workflow_scope="org",
        workflow_execution_id=execution_id,
        workflow_action_index=2,
    )
    second = adapter.execute_action(
        db=db,
        action={
            "action_type": "send_message",
            "purpose": "operational",
            "message_template_version_id": str(template.id),
        },
        entity=surrogate,
        entity_type="surrogate",
        event_id=uuid4(),
        depth=0,
        workflow_scope="org",
        workflow_execution_id=execution_id,
        workflow_action_index=2,
    )

    assert first["success"] is True
    assert second["delivery_id"] == first["delivery_id"]
    delivery = db.query(MessageDelivery).filter(MessageDelivery.id == first["delivery_id"]).one()
    assert delivery.idempotency_key == f"workflow-message/{execution_id}/action/2"
    assert delivery.template_version_id == template.id


def test_send_message_workflow_rejects_stale_contact_after_entity_phone_changes(
    db,
    test_org,
    test_user,
    default_stage,
):
    from app.core.encryption import hash_phone
    from app.db.models import MessageDelivery
    from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter

    template = _published_message_template(
        db,
        test_org,
        test_user,
        purpose="operational",
        body="Operational update. Reply STOP to opt out.",
    )
    template.is_enrollment_confirmation = True
    surrogate = _messaging_surrogate(db, test_org, test_user, default_stage)
    _consent_for_surrogate(db, test_org, surrogate, purpose="operational")
    surrogate.phone = "+14155550186"
    surrogate.phone_hash = hash_phone(surrogate.phone)
    db.flush()

    result = DefaultWorkflowDomainAdapter().execute_action(
        db=db,
        action={
            "action_type": "send_message",
            "purpose": "operational",
            "message_template_version_id": str(template.id),
        },
        entity=surrogate,
        entity_type="surrogate",
        event_id=uuid4(),
        depth=0,
        workflow_scope="org",
        workflow_execution_id=uuid4(),
        workflow_action_index=0,
    )

    assert result == {
        "success": False,
        "error": "No consented messaging contact resolved",
        "skipped": True,
    }
    assert (
        db.query(MessageDelivery).filter(MessageDelivery.organization_id == test_org.id).count()
        == 0
    )
