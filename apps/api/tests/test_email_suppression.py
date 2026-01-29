"""Tests for global email suppression behavior."""

import pytest


def test_send_email_skips_suppressed(db, test_org):
    from app.services import email_service, campaign_service
    from app.db.enums import EmailStatus
    from app.db.models import Job

    campaign_service.add_to_suppression(
        db,
        org_id=test_org.id,
        email="suppressed@example.com",
        reason="opt_out",
    )

    email_log, job = email_service.send_email(
        db=db,
        org_id=test_org.id,
        template_id=None,
        recipient_email="suppressed@example.com",
        subject="Hello",
        body="<p>Hi</p>",
    )

    assert job is None
    assert email_log.status == EmailStatus.SKIPPED.value
    assert "suppressed" in (email_log.error or "").lower()
    assert email_log.job_id is None

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

    def fail_resolve(*args, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("Provider resolution should not be called for suppressed emails")

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        fail_resolve,
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
