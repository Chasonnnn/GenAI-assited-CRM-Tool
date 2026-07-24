"""Tests for global email suppression behavior."""

import pytest


def test_send_email_skips_suppressed(db, test_org):
    from uuid import uuid4

    from app.services import campaign_service, email_service, resend_settings_service
    from app.db.enums import EmailStatus
    from app.db.models import Job, ResendSettings

    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_key"),
            from_email="care@example.com",
            verified_domain="example.com",
        )
    )
    db.flush()

    campaign_service.add_to_suppression(
        db,
        org_id=test_org.id,
        email="suppressed@example.com",
        reason="opt_out",
    )
    occurrence_key = f"suppressed-email/{uuid4()}"

    email_log, delivery = email_service.send_email(
        db=db,
        org_id=test_org.id,
        template_id=None,
        recipient_email="suppressed@example.com",
        subject="Hello",
        body="<p>Hi</p>",
        idempotency_key=occurrence_key,
    )
    retried_log, retried_delivery = email_service.send_email(
        db=db,
        org_id=test_org.id,
        template_id=None,
        recipient_email="suppressed@example.com",
        subject="Hello",
        body="<p>Hi</p>",
        idempotency_key=occurrence_key,
    )

    assert delivery is None
    assert retried_delivery is None
    assert retried_log.id == email_log.id
    assert email_log.status == EmailStatus.SKIPPED.value
    assert "suppressed" in (email_log.error or "").lower()
    assert email_log.job_id is None
    assert email_log.idempotency_key == occurrence_key
    assert email_log.provider == "resend"
    assert email_log.provider_account_id == f"organization:{test_org.id}"
    assert email_log.source_type == "organization_email"

    jobs = db.query(Job).filter(Job.organization_id == test_org.id).all()
    assert jobs == []


@pytest.mark.asyncio
async def test_workflow_email_skips_suppressed(db, test_org, test_user, monkeypatch):
    from uuid import uuid4
    from app.db.models import Job
    from app.db.enums import JobType
    from app.services import email_service, campaign_service
    from app.worker import process_workflow_email
    from app.services import workflow_email_provider

    template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Workflow Template",
        subject="Hello {{full_name}}",
        body="<p>Welcome {{full_name}}</p>",
    )

    campaign_service.add_to_suppression(
        db,
        org_id=test_org.id,
        email="suppressed@example.com",
        reason="opt_out",
    )

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **_kwargs: (
            "resend",
            {
                "api_key_encrypted": "write-only",
                "from_email": "care@example.com",
                "from_name": "Care Team",
                "reply_to": None,
            },
        ),
    )

    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "suppressed@example.com",
            "variables": {"full_name": "Suppressed User"},
        },
    )
    db.add(job)
    db.commit()

    await process_workflow_email(db, job)

    from app.db.models import EmailLog

    email_log = (
        db.query(EmailLog)
        .filter(EmailLog.organization_id == test_org.id)
        .order_by(EmailLog.created_at.desc())
        .first()
    )
    assert email_log is not None
    assert email_log.status == "skipped"
    assert "suppressed" in (email_log.error or "").lower()
