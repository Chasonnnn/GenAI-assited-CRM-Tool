"""Default personal authoring does not grant shared writes or record access."""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.encryption import hash_email
from app.db.enums import Role
from app.db.models import (
    EmailTemplate,
    Membership,
    Organization,
    Pipeline,
    PipelineStage,
    PlatformEmailTemplate,
    PlatformEmailTemplateTarget,
    RolePermission,
    RoleRecordScope,
    Surrogate,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.routers import email_templates
from app.schemas.auth import UserSession
from app.schemas.email import EmailSendRequest, EmailTemplateCopyRequest


@pytest.fixture
def actor(db, test_org, test_user):
    member = db.query(Membership).filter_by(user_id=test_user.id).one()
    member.role = Role.INTAKE_SPECIALIST.value
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.add(
        RoleRecordScope(
            organization_id=test_org.id,
            role=member.role,
            module="surrogates",
            assignment="assigned",
            phase="all",
        )
    )
    for key in ("manage_email_templates", "send_email"):
        db.add(
            RolePermission(
                organization_id=test_org.id, role=member.role, permission=key, is_granted=True
            )
        )
    db.flush()
    return UserSession(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.INTAKE_SPECIALIST,
        email=test_user.email,
        display_name=test_user.display_name,
    )


def allow_org_templates(db, actor):
    db.add(
        RolePermission(
            organization_id=actor.org_id,
            role=actor.role.value,
            permission="manage_org_templates",
            is_granted=True,
        )
    )
    db.flush()


def library_template(db, *, globally=True, published=True):
    row = PlatformEmailTemplate(
        id=uuid4(),
        name="Shared library example",
        subject="Hello",
        body="<p>Hello</p>",
        status="published" if published else "draft",
        current_version=1,
        published_version=1 if published else 0,
        is_published_globally=globally,
    )
    db.add(row)
    db.flush()
    return row


def test_library_copy_requires_org_management_before_lookup(db, actor, monkeypatch):
    lookup = Mock(side_effect=AssertionError("Unauthorized copy must not inspect library content"))
    monkeypatch.setattr(
        "app.services.platform_template_service.get_published_email_template_for_org", lookup
    )
    with pytest.raises(HTTPException) as error:
        email_templates.copy_platform_email_template(
            uuid4(), EmailTemplateCopyRequest(name="Copy"), db, actor
        )
    assert error.value.status_code == 403
    lookup.assert_not_called()


def test_library_copy_with_org_grant_uses_authenticated_organization(db, actor):
    allow_org_templates(db, actor)
    library = library_template(db)
    result = email_templates.copy_platform_email_template(
        library.id, EmailTemplateCopyRequest(name="Org copy"), db, actor
    )
    saved = db.get(EmailTemplate, result.id)
    assert saved.organization_id == actor.org_id
    assert saved.scope == "org"


@pytest.mark.parametrize("foreign", [False, True])
def test_library_copy_hides_unpublished_or_other_org_targets(db, actor, foreign):
    allow_org_templates(db, actor)
    library = library_template(db, globally=False, published=foreign)
    if foreign:
        other = Organization(id=uuid4(), name="Other QA", slug=f"other-{uuid4().hex[:12]}")
        db.add(other)
        db.flush()
        db.add(PlatformEmailTemplateTarget(template_id=library.id, organization_id=other.id))
        db.flush()
    with pytest.raises(HTTPException) as error:
        email_templates.copy_platform_email_template(
            library.id, EmailTemplateCopyRequest(name="Copy"), db, actor
        )
    assert error.value.status_code == 404


def make_record(db, actor, default_stage, *, accessible=True, foreign=False):
    org_id = actor.org_id
    stage = default_stage
    if foreign:
        other = Organization(id=uuid4(), name="Other QA", slug=f"other-{uuid4().hex[:12]}")
        db.add(other)
        db.flush()
        org_id = other.id
        pipeline = Pipeline(
            id=uuid4(), organization_id=other.id, name="QA pipeline", is_default=True
        )
        db.add(pipeline)
        db.flush()
        stage = PipelineStage(
            id=uuid4(),
            pipeline_id=pipeline.id,
            slug="new_unread",
            label="New Unread",
            color="#3B82F6",
            stage_type="intake",
            order=1,
            is_active=True,
        )
        db.add(stage)
        db.flush()
    email = f"qa-{uuid4().hex[:8]}@example.com"
    row = Surrogate(
        id=uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid4().int % 90000 + 10000}",
        full_name="Synthetic Applicant",
        email=email,
        email_hash=hash_email(email),
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=actor.user_id if accessible else uuid4(),
    )
    db.add(row)
    db.flush()
    return row


@pytest.mark.parametrize(
    "accessible,foreign,allowed", [(True, False, True), (False, False, False), (True, True, False)]
)
def test_template_send_rechecks_record_scope_before_delivery(
    db, actor, default_stage, monkeypatch, accessible, foreign, allowed
):
    record = make_record(db, actor, default_stage, accessible=accessible, foreign=foreign)
    template = EmailTemplate(
        id=uuid4(),
        organization_id=actor.org_id,
        name="Personal draft",
        subject="Hello",
        body="<p>Hello</p>",
        scope="personal",
        owner_user_id=actor.user_id,
        created_by_user_id=actor.user_id,
        is_active=True,
    )
    db.add(template)
    db.flush()
    queued = Mock(return_value=(object(), None))
    monkeypatch.setattr(email_templates.email_service, "send_from_template", queued)
    request = EmailSendRequest(
        template_id=template.id,
        recipient_email=record.email,
        variables={},
        surrogate_id=record.id,
        idempotency_key=str(uuid4()),
    )
    if allowed:
        email_templates.send_email(request, db, actor)
        assert queued.call_args.kwargs["org_id"] == actor.org_id
        assert queued.call_args.kwargs["surrogate_id"] == record.id
    else:
        with pytest.raises(HTTPException) as error:
            email_templates.send_email(request, db, actor)
        assert error.value.status_code in (403, 404)
        queued.assert_not_called()
