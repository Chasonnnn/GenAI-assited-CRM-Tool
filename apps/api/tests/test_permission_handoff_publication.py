"""Approval and publication behavior under the reviewed permission model."""

from uuid import uuid4

import pytest

from app.db.enums import Role
from app.db.models import (
    Donor,
    EmailTemplate,
    Membership,
    OrganizationPermissionPolicy,
    PipelineStage,
    RecordCollaborator,
    User,
    UserPermissionOverride,
)
from app.schemas.auth import UserSession
from app.services import (
    donor_service,
    email_template_publication,
    pipeline_service,
    record_scope_service,
)


def member(db, org_id, role):
    user = User(
        id=uuid4(), email=f"{uuid4()}@test.invalid", display_name="Test staff", is_active=True
    )
    db.add(user)
    db.flush()
    db.add(Membership(organization_id=org_id, user_id=user.id, role=role.value, is_active=True))
    db.flush()
    return user


def session(org_id, user, role):
    return UserSession(org_id=org_id, user_id=user.id, role=role, email="", display_name="")


@pytest.mark.parametrize("donor_type", ["egg", "sperm"])
def test_approval_retains_intake_and_enters_pool(db, test_org, donor_type):
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    manager = member(db, test_org.id, Role.CASE_MANAGER)
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type=f"{donor_type}_donor"
    )
    stages = {s.stage_key: s for s in db.query(PipelineStage).filter_by(pipeline_id=pipeline.id)}
    donor = Donor(
        id=uuid4(),
        organization_id=test_org.id,
        donor_number="D10001",
        donor_type=donor_type,
        full_name="Synthetic Applicant",
        email=f"{uuid4()}@test.invalid",
        email_hash=uuid4().hex,
        owner_type="user",
        owner_id=intake.id,
        stage_id=stages["new"].id,
    )
    db.add(donor)
    db.flush()
    donor_service.change_status(
        db,
        donor,
        stages["approved"].id,
        intake.id,
        user_role=Role.INTAKE_SPECIALIST,
        emit_workflow_events=False,
    )
    assert donor.owner_type == "queue"
    assert db.query(RecordCollaborator).filter_by(donor_id=donor.id, user_id=intake.id).count() == 1
    assert record_scope_service.can_access_record(
        db, session(test_org.id, intake, Role.INTAKE_SPECIALIST), "donor", donor
    )
    assert record_scope_service.can_access_record(
        db, session(test_org.id, manager, Role.CASE_MANAGER), "donor", donor
    )
    assert stages["approved"].stage_type == "post_approval"


def test_stage_edit_does_not_grant_applicant_approval(db, test_org):
    user = member(db, test_org.id, Role.CASE_MANAGER)
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor"
    )
    stages = {s.stage_key: s for s in db.query(PipelineStage).filter_by(pipeline_id=pipeline.id)}
    donor = Donor(
        id=uuid4(),
        organization_id=test_org.id,
        donor_number="D10002",
        donor_type="egg",
        full_name="Synthetic Applicant",
        email=f"{uuid4()}@test.invalid",
        email_hash=uuid4().hex,
        owner_type="user",
        owner_id=user.id,
        stage_id=stages["new"].id,
    )
    db.add(donor)
    db.flush()
    with pytest.raises(ValueError, match="approval permission"):
        donor_service.change_status(
            db,
            donor,
            stages["ready_to_match"].id,
            user.id,
            user_role=Role.CASE_MANAGER,
            emit_workflow_events=False,
            execution_permissions=frozenset({"change_donor_status"}),
        )
    assert donor.stage_id == stages["new"].id
    assert db.query(RecordCollaborator).filter_by(donor_id=donor.id).count() == 0


def test_publication_is_independent_and_keeps_proposer_credit(db, test_org):
    proposer = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    admin = member(db, test_org.id, Role.ADMIN)
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    source = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=proposer.id,
        scope="personal",
        owner_user_id=proposer.id,
        name="Private source",
        subject="Original",
        body="<p>Original</p>",
        is_active=True,
    )
    db.add(source)
    db.flush()
    published = email_template_publication.publish_template_to_org(
        db, org_id=test_org.id, template_id=source.id, actor_user_id=admin.id
    )
    assert published.scope == "org" and published.owner_user_id is None
    assert published.source_template_id is None
    assert published.proposed_by_user_id == proposer.id
    assert published.proposed_by_name == proposer.display_name
    source.body = "Changed private source"
    db.query(Membership).filter_by(user_id=proposer.id).one().is_active = False
    db.flush()
    assert published.body == "<p>Original</p>"
    assert published.is_active
    from app.db.models import AuditLog, EntityVersion
    from app.services import version_service

    version = (
        db.query(EntityVersion)
        .filter_by(
            organization_id=test_org.id, entity_type="email_template", entity_id=published.id
        )
        .one()
    )
    assert version.version == 1
    assert version_service.decrypt_payload(version.payload_encrypted)["body"] == "<p>Original</p>"
    private_access = (
        db.query(AuditLog)
        .filter_by(organization_id=test_org.id, actor_user_id=admin.id, target_id=source.id)
        .all()
    )
    assert any(row.details == {"operation": "private_template_access"} for row in private_access)


def test_personal_publication_needs_org_authority(db, test_org):
    owner = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    source = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=owner.id,
        scope="personal",
        owner_user_id=owner.id,
        name="Personal",
        subject="Subject",
        body="Body",
    )
    db.add(source)
    db.flush()
    with pytest.raises(PermissionError):
        email_template_publication.publish_template_to_org(
            db, org_id=test_org.id, template_id=source.id, actor_user_id=owner.id
        )
    db.add(
        UserPermissionOverride(
            organization_id=test_org.id,
            user_id=owner.id,
            permission="manage_org_templates",
            override_type="grant",
        )
    )
    db.flush()
    assert (
        email_template_publication.publish_template_to_org(
            db, org_id=test_org.id, template_id=source.id, actor_user_id=owner.id
        ).scope
        == "org"
    )


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
@pytest.mark.parametrize(
    "phase_stage,prior,expected",
    [
        ("on_hold", "new", True),
        ("on_hold", "approved", False),
        ("rejected", None, True),
    ],
)
def test_paused_and_unknown_terminal_cannot_bypass_approval(
    db, test_org, kind, phase_stage, prior, expected
):
    from app.services import approval_handoff_service
    from tests.test_record_scopes_v2 import _record

    user = member(db, test_org.id, Role.ADMIN)
    actor = session(test_org.id, user, Role.ADMIN)
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, entity_type="egg_donor" if kind == "donor" else kind
    )
    stages = {s.stage_key: s for s in pipeline.stages}
    phase_type = "paused" if phase_stage == "on_hold" else "terminal"
    stage = next(s for s in stages.values() if s.stage_type == phase_type)
    record = _record(db, actor, kind, key=stage.stage_key)
    if prior:
        prior_stage = (
            stages["approved"]
            if prior == "approved"
            else min(stages.values(), key=lambda s: s.order)
        )
        record.paused_from_stage_id = prior_stage.id
        db.flush()
    assert approval_handoff_service.crosses_approval(db, record, stages["approved"]) is expected


@pytest.mark.asyncio
async def test_donor_claim_is_scoped_and_requires_csrf(db, test_org):
    from app.core.csrf import CSRF_HEADER
    from app.services import queue_service
    from tests.test_email_templates_personal_scope import authed_client_for_user
    from tests.test_record_scopes_v2 import _record

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    manager = member(db, test_org.id, Role.CASE_MANAGER)
    actor = session(test_org.id, manager, Role.CASE_MANAGER)
    donor = _record(db, actor, "donor", key="approved")
    pool = queue_service.create_queue(db, test_org.id, "Donor Pool")
    donor.owner_type, donor.owner_id = "queue", pool.id
    db.flush()
    async with authed_client_for_user(db, test_org.id, manager, Role.CASE_MANAGER) as client:
        denied = await client.post(f"/donors/{donor.id}/claim", headers={CSRF_HEADER: ""})
        assert denied.status_code == 403
        missing = await client.post(f"/donors/{uuid4()}/claim")
        assert missing.status_code == 404
        result = await client.post(f"/donors/{donor.id}/claim")
        assert result.status_code == 200, result.text
        assert result.json()["owner_id"] == str(manager.id)
        again = await client.post(f"/donors/{donor.id}/claim")
        assert again.status_code == 409


@pytest.mark.asyncio
async def test_collaborator_options_and_names_are_scoped_to_accessible_record(db, test_org):
    from app.db.models import Organization
    from tests.test_email_templates_personal_scope import authed_client_for_user
    from tests.test_record_scopes_v2 import _record

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    manager = member(db, test_org.id, Role.CASE_MANAGER)
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    actor = session(test_org.id, manager, Role.CASE_MANAGER)
    donor = _record(db, actor, "donor", key="approved")
    hidden = _record(db, session(test_org.id, intake, Role.INTAKE_SPECIALIST), "donor", suffix=2)
    other_org = Organization(id=uuid4(), slug=f"other-{uuid4().hex}", name="Other agency")
    db.add(other_org)
    db.flush()
    outsider = member(db, other_org.id, Role.INTAKE_SPECIALIST)
    other_record = _record(db, session(other_org.id, outsider, Role.INTAKE_SPECIALIST), "donor")
    async with authed_client_for_user(db, test_org.id, manager, Role.CASE_MANAGER) as client:
        path = f"/record-scopes/records/donor/{donor.id}"
        options = await client.get(f"{path}/collaborator-options")
        assert options.status_code == 200, options.text
        assert [row["user_id"] for row in options.json()] == [str(intake.id)]
        assert (
            await client.get(f"/record-scopes/records/donor/{hidden.id}/collaborator-options")
        ).status_code == 403
        assert (
            await client.get(f"/record-scopes/records/donor/{other_record.id}/collaborator-options")
        ).status_code == 404
        assert (await client.post(f"/donors/{other_record.id}/claim")).status_code == 404
        created = await client.post(f"{path}/collaborators", json={"user_id": str(intake.id)})
        assert created.status_code == 201, created.text
        rows = await client.get(f"{path}/collaborators")
        assert rows.json()[0]["display_name"] == intake.display_name


@pytest.mark.asyncio
async def test_admin_private_template_listing_is_audited_without_content(db, test_org):
    from app.db.models import AuditLog
    from tests.test_email_templates_personal_scope import authed_client_for_user

    owner = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    admin = member(db, test_org.id, Role.ADMIN)
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    template = EmailTemplate(
        organization_id=test_org.id,
        created_by_user_id=owner.id,
        owner_user_id=owner.id,
        scope="personal",
        name="Private content",
        subject="Confidential subject",
        body="Confidential body",
        is_active=True,
    )
    db.add(template)
    db.flush()
    async with authed_client_for_user(db, test_org.id, admin, Role.ADMIN) as client:
        response = await client.get("/email-templates?scope=personal&show_all_personal=true")
        assert response.status_code == 200, response.text
        audit = (
            db.query(AuditLog).filter_by(organization_id=test_org.id, target_id=template.id).one()
        )
        assert audit.actor_user_id == admin.id
        assert audit.details == {"operation": "private_template_access"}


def test_surrogate_approval_retains_intake_without_committing(db, test_org):
    from app.services import surrogate_status_service
    from tests.test_record_scopes_v2 import _record

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    actor = session(test_org.id, intake, Role.INTAKE_SPECIALIST)
    surrogate = _record(db, actor, "surrogate")
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    approved = next(stage for stage in pipeline.stages if stage.stage_key == "approved")
    surrogate_status_service.change_status(
        db,
        surrogate,
        approved.id,
        intake.id,
        Role.INTAKE_SPECIALIST,
        trigger_workflows=False,
        commit=False,
    )
    assert surrogate.owner_type == "queue"
    assert (
        db.query(RecordCollaborator).filter_by(surrogate_id=surrogate.id, user_id=intake.id).count()
        == 1
    )
    assert record_scope_service.can_access_record(db, actor, "surrogate", surrogate)


@pytest.mark.asyncio
async def test_readonly_donor_detail_resolves_only_same_org_owner_name(db, test_org):
    from app.db.models import Organization
    from tests.test_email_templates_personal_scope import authed_client_for_user
    from tests.test_record_scopes_v2 import _record

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    viewer = member(db, test_org.id, Role.OPERATIONS)
    donor = _record(db, session(test_org.id, intake, Role.INTAKE_SPECIALIST), "donor")
    async with authed_client_for_user(db, test_org.id, viewer, Role.OPERATIONS) as client:
        response = await client.get(f"/donors/{donor.id}")
        assert response.status_code == 200, response.text
        assert response.json()["owner_name"] == intake.display_name
        assert (await client.get("/donors/owner-options")).status_code == 403
        other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
        db.add(other)
        db.flush()
        outsider = member(db, other.id, Role.INTAKE_SPECIALIST)
        donor.owner_id = outsider.id
        db.flush()
        response = await client.get(f"/donors/{donor.id}")
        assert response.json()["owner_name"] is None
