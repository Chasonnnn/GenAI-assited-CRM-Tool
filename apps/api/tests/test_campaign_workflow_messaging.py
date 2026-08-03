from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError


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
