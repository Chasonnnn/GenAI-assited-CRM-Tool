from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_workflow_email_appends_org_signature_for_org_scope(
    db, test_org, test_user, monkeypatch
):
    from app.db.enums import JobType
    from app.db.models import EmailLog, EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email
    from app.services import resend_email_service, resend_settings_service

    test_org.signature_company_name = "Org Signature Co"
    test_org.signature_template = "classic"
    db.commit()

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Workflow Template",
        subject="Hello",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.commit()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **kwargs: (
            "resend",
            {"api_key_encrypted": "fake", "from_email": "no-reply@test.com"},
        ),
    )
    monkeypatch.setattr(resend_settings_service, "decrypt_api_key", lambda _: "key")

    async def fake_send_email_direct(**_kwargs):
        return True, None, "msg-id"

    monkeypatch.setattr(resend_email_service, "send_email_direct", fake_send_email_direct)

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@test.com",
            "variables": {},
            "workflow_scope": "org",
            "include_org_signature": True,
        },
    )
    db.add(job)
    db.commit()

    await process_workflow_email(db, job)

    email_log = (
        db.query(EmailLog)
        .filter(EmailLog.organization_id == test_org.id)
        .order_by(EmailLog.created_at.desc())
        .first()
    )
    assert email_log is not None
    assert "Org Signature Co" in (email_log.body or "")
    assert test_user.display_name not in (email_log.body or "")
    assert ">Unsubscribe<" in (email_log.body or "")
    assert "/email/unsubscribe/" in (email_log.body or "")


@pytest.mark.asyncio
async def test_workflow_email_appends_personal_signature_for_personal_scope(
    db, test_org, test_user, monkeypatch
):
    from app.db.enums import JobType
    from app.db.models import EmailLog, EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email
    from app.services import resend_email_service, resend_settings_service

    test_org.signature_company_name = "Org Signature Co"
    test_org.signature_template = "classic"
    db.commit()

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Workflow Template",
        subject="Hello",
        body="<p>Body</p>",
        scope="personal",
        owner_user_id=test_user.id,
        is_active=True,
    )
    db.add(template)
    db.commit()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **kwargs: (
            "resend",
            {"api_key_encrypted": "fake", "from_email": "no-reply@test.com"},
        ),
    )
    monkeypatch.setattr(resend_settings_service, "decrypt_api_key", lambda _: "key")

    async def fake_send_email_direct(**_kwargs):
        return True, None, "msg-id"

    monkeypatch.setattr(resend_email_service, "send_email_direct", fake_send_email_direct)

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@test.com",
            "variables": {},
            "workflow_scope": "personal",
            "workflow_owner_id": str(test_user.id),
            "include_org_signature": True,
        },
    )
    db.add(job)
    db.commit()

    await process_workflow_email(db, job)

    email_log = (
        db.query(EmailLog)
        .filter(EmailLog.organization_id == test_org.id)
        .order_by(EmailLog.created_at.desc())
        .first()
    )
    assert email_log is not None
    assert "Org Signature Co" in (email_log.body or "")
    assert test_user.display_name in (email_log.body or "")
    assert ">Unsubscribe<" in (email_log.body or "")
    assert "/email/unsubscribe/" in (email_log.body or "")


@pytest.mark.asyncio
async def test_workflow_email_logs_surrogate_activity_and_audit_after_success_with_system_actor_fallback(
    db, test_org, test_user, monkeypatch
):
    from app.core.constants import SYSTEM_USER_ID
    from app.db.enums import AuditEventType, JobType, SurrogateSource, SurrogateActivityType
    from app.db.models import AuditLog, EmailTemplate, Job, SurrogateActivityLog
    from app.schemas.surrogate import SurrogateCreate
    from app.services import workflow_email_provider
    from app.services import surrogate_service
    from app.worker import process_workflow_email
    from app.services import resend_email_service, resend_settings_service

    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(
            full_name="Workflow Surrogate",
            email="workflow-surrogate@test.com",
            source=SurrogateSource.MANUAL,
        ),
    )

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Workflow Template",
        subject="Follow up {{full_name}}",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.commit()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **kwargs: (
            "resend",
            {"api_key_encrypted": "fake", "from_email": "no-reply@test.com"},
        ),
    )
    monkeypatch.setattr(resend_settings_service, "decrypt_api_key", lambda _: "key")

    async def fake_send_email_direct(**_kwargs):
        return True, None, "msg-id"

    monkeypatch.setattr(resend_email_service, "send_email_direct", fake_send_email_direct)

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@test.com",
            "variables": {},
            "workflow_scope": "org",
            "surrogate_id": str(surrogate.id),
        },
    )
    db.add(job)
    db.commit()

    await process_workflow_email(db, job)

    activity = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == surrogate.id,
            SurrogateActivityLog.activity_type == SurrogateActivityType.EMAIL_SENT.value,
        )
        .order_by(SurrogateActivityLog.created_at.desc())
        .first()
    )
    assert activity is not None
    details = activity.details or {}
    assert details.get("provider") == "resend"
    assert details.get("template_id") == str(template.id)
    assert details.get("subject", "").startswith("Follow up")

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == AuditEventType.DATA_EMAIL_SENT.value,
            AuditLog.target_type == "surrogate",
            AuditLog.target_id == surrogate.id,
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.actor_user_id == SYSTEM_USER_ID


@pytest.mark.asyncio
async def test_workflow_email_rejects_platform_system_template(
    db, test_org, test_user, monkeypatch
):
    from app.db.enums import JobType
    from app.db.models import EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Organization Invite",
        subject="Invitation to join {{org_name}} as {{role_title}}",
        body="<p>Invite</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
        is_system_template=True,
        system_key="org_invite",
    )
    db.add(template)
    db.commit()

    def fail_resolve(*_args, **_kwargs):  # pragma: no cover - should not be called
        raise AssertionError("Provider resolution should not be called for platform templates")

    monkeypatch.setattr(workflow_email_provider, "resolve_workflow_email_provider", fail_resolve)

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@test.com",
            "variables": {},
            "workflow_scope": "org",
        },
    )
    db.add(job)
    db.commit()

    with pytest.raises(Exception) as exc_info:
        await process_workflow_email(db, job)

    assert "platform" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_workflow_email_rejects_org_gmail_provider_for_org_scope(
    db, test_org, test_user, monkeypatch
):
    from app.db.enums import JobType
    from app.db.models import EmailTemplate, Job
    from app.services import workflow_email_provider
    from app.worker import process_workflow_email

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        name="Org Workflow Resend Only",
        subject="Hello",
        body="<p>Body</p>",
        scope="org",
        owner_user_id=None,
        is_active=True,
    )
    db.add(template)
    db.commit()

    monkeypatch.setattr(
        workflow_email_provider,
        "resolve_workflow_email_provider",
        lambda **kwargs: (
            "org_gmail",
            {"sender_user_id": test_user.id, "email": test_user.email},
        ),
    )

    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template.id),
            "recipient_email": "recipient@test.com",
            "variables": {},
            "workflow_scope": "org",
        },
    )
    db.add(job)
    db.commit()

    with pytest.raises(Exception) as exc_info:
        await process_workflow_email(db, job)

    assert "resend" in str(exc_info.value).lower()
