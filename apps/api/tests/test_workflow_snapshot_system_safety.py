"""Queue and worker safety for platform/system workflow email templates."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest


def test_workflow_queue_rejects_platform_system_template_before_scheduling(
    db,
    test_org,
) -> None:
    from app.db.enums import JobType
    from app.db.models import EmailTemplate, Job
    from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter

    template = EmailTemplate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Legacy Organization Invite",
        subject="Invitation to join {{org_name}}",
        body="<p>Accept at {{invite_url}}</p>",
        scope="org",
        is_active=True,
        is_system_template=True,
        system_key="org_invite",
    )
    db.add(template)
    db.commit()

    entity = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        email="must-not-queue@example.test",
        owner_type=None,
        owner_id=None,
        created_by_user_id=None,
    )
    result = DefaultWorkflowDomainAdapter().execute_action(
        db=db,
        action={
            "action_type": "send_email",
            "template_id": str(template.id),
            "recipients": "surrogate",
        },
        entity=entity,
        entity_type="surrogate",
        event_id=uuid.uuid4(),
        depth=0,
        workflow_scope="org",
        workflow_owner_id=None,
    )

    assert result["success"] is False
    assert "Platform system template 'org_invite'" in result["error"]

    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_EMAIL.value,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_workflow_worker_rejects_platform_system_template_snapshot(
    db,
    test_org,
) -> None:
    """A snapshot must retain enough provenance for the worker to fail closed."""
    from app.db.enums import JobType
    from app.db.models import EmailLog, Job
    from app.jobs.handlers.email import process_workflow_email

    template_id = uuid.uuid4()
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template_id),
            "recipient_email": "must-not-send@example.test",
            "variables": {},
            "workflow_scope": "org",
            "workflow_owner_id": None,
            "email_template_snapshot": {
                "schema_version": 1,
                "organization_id": str(test_org.id),
                "template_id": str(template_id),
                "template_version": 4,
                "subject": "Platform-only subject",
                "body": "<p>Platform-only body</p>",
                "from_email": "Platform <platform@example.test>",
                "scope": "org",
                "owner_user_id": None,
                "system_key": "org_invite",
            },
        },
    )
    db.add(job)
    db.commit()

    with pytest.raises(Exception, match="Platform system template 'org_invite'"):
        await process_workflow_email(db, job)

    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_workflow_worker_rejects_snapshot_without_system_provenance(
    db,
    test_org,
) -> None:
    from app.db.enums import JobType
    from app.db.models import EmailLog, Job
    from app.jobs.handlers.email import process_workflow_email
    from app.services.email_template_snapshot import EmailTemplateSnapshotError

    template_id = uuid.uuid4()
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "template_id": str(template_id),
            "recipient_email": "missing-provenance@example.test",
            "variables": {},
            "workflow_scope": "org",
            "workflow_owner_id": None,
            "email_template_snapshot": {
                "schema_version": 1,
                "organization_id": str(test_org.id),
                "template_id": str(template_id),
                "template_version": 4,
                "subject": "Unclassified subject",
                "body": "<p>Unclassified body</p>",
                "from_email": "Sender <sender@example.test>",
                "scope": "org",
                "owner_user_id": None,
            },
        },
    )
    db.add(job)
    db.commit()

    with pytest.raises(EmailTemplateSnapshotError, match="snapshot is invalid"):
        await process_workflow_email(db, job)

    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.source_type == "workflow_job",
            EmailLog.source_id == job.id,
        )
        .count()
        == 0
    )
