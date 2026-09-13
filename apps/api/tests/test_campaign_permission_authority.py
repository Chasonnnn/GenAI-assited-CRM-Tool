"""Permission v2 campaign ownership, audience and delivery contracts."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.encryption import hash_email
from app.db.enums import Role
from app.db.models import (
    Campaign,
    CampaignRecipient,
    CampaignRun,
    EmailTemplate,
    Membership,
    Organization,
    Surrogate,
    User,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.db.models.record_access import RecordCollaborator, RoleRecordScope
from app.schemas.campaign import CampaignCreate
from app.services import campaign_access, campaign_service
from app.services.workflow_execution_authority import active_session


@pytest.fixture
def setup(db, test_org, test_user, default_stage, monkeypatch):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    template = EmailTemplate(
        id=uuid4(),
        organization_id=test_org.id,
        name="Campaign template",
        subject="Hello",
        body="<p>Hello</p>",
        scope="org",
        created_by_user_id=test_user.id,
        is_active=True,
    )
    record = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        full_name="Assigned Recipient",
        email="assigned-campaign@example.com",
        email_hash=hash_email("assigned-campaign@example.com"),
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
    )
    db.add_all([template, record])
    db.flush()
    monkeypatch.setattr(
        "app.services.email_provider_service.resolve_campaign_provider",
        lambda *_args: ("resend", SimpleNamespace(from_email="care@example.com", from_name="Care")),
    )
    return test_org, test_user, template, record


def create(db, org, owner, template, *, scope="personal"):
    return campaign_service.create_campaign(
        db,
        org.id,
        owner.id,
        CampaignCreate(
            name=f"Campaign {uuid4()}",
            scope=scope,
            email_template_id=template.id,
            recipient_type="case",
        ),
    )


def staff(db, org):
    user = User(
        id=uuid4(), email=f"staff-{uuid4()}@example.com", display_name="Staff", is_active=True
    )
    db.add(user)
    db.flush()
    membership = Membership(
        id=uuid4(),
        user_id=user.id,
        organization_id=org.id,
        role=Role.INTAKE_SPECIALIST.value,
        is_active=True,
    )
    db.add(membership)
    db.add(
        RoleRecordScope(
            organization_id=org.id,
            role=Role.INTAKE_SPECIALIST.value,
            module="surrogates",
            assignment="all",
            phase="all",
        )
    )
    db.flush()
    return user, membership


def enqueue(db, campaign, user):
    _, run_id, _ = campaign_service.enqueue_campaign_send(
        db, campaign.organization_id, campaign.id, user.id
    )
    db.flush()
    return db.get(CampaignRun, run_id)


def recipient(db, run, record):
    row = CampaignRecipient(
        run_id=run.id,
        entity_type="case",
        entity_id=record.id,
        recipient_email=record.email,
        recipient_name=record.full_name,
        status="pending",
    )
    db.add(row)
    db.flush()
    return row


def test_personal_campaigns_are_private_but_admin_can_manage(setup, db):
    org, admin, template, _ = setup
    owner, _ = staff(db, org)
    private = create(db, org, admin, template)
    own = create(db, org, owner, template)
    session = active_session(db, org.id, owner.id)
    listed, total = campaign_service.list_campaigns(db, org.id, viewer_session=session)
    assert [row.id for row in listed] == [own.id]
    assert total == 1
    assert not campaign_access.can_view(db, session, private)
    assert not campaign_access.can_manage(db, session, private)
    assert campaign_access.can_manage(db, active_session(db, org.id, admin.id), own)


def test_edit_campaigns_does_not_grant_send(setup, db):
    org, _, template, _ = setup
    owner, _ = staff(db, org)
    campaign = create(db, org, owner, template)
    session = active_session(db, org.id, owner.id)
    assert campaign_access.can_manage(db, session, campaign, "edit")
    assert not campaign_access.can_manage(db, session, campaign, "send")
    with pytest.raises(ValueError, match="Missing permission"):
        enqueue(db, campaign, owner)
    assert db.query(CampaignRun).filter_by(campaign_id=campaign.id).count() == 0


def test_saved_and_unsaved_personal_preview_only_assigned_or_collaborator(setup, db):
    org, admin, template, record = setup
    owner, membership = staff(db, org)
    campaign = create(db, org, owner, template)
    empty = campaign_service.preview_recipients(db, org.id, "case", {}, campaign=campaign)
    assert empty.total_count == 0
    link = RecordCollaborator(
        organization_id=org.id,
        user_id=owner.id,
        membership_id=membership.id,
        surrogate_id=record.id,
        granted_by_user_id=admin.id,
    )
    db.add(link)
    db.flush()
    saved = campaign_service.preview_recipients(db, org.id, "case", {}, campaign=campaign)
    unsaved = campaign_service.preview_recipients(
        db, org.id, "case", {}, scope="personal", owner_user_id=owner.id
    )
    assert saved.total_count == unsaved.total_count == 1
    assert saved.sample_recipients[0].entity_id == record.id


def test_org_send_survives_original_actor_departure(setup, db):
    org, actor, template, record = setup
    campaign = create(db, org, actor, template, scope="org")
    run = enqueue(db, campaign, actor)
    row = recipient(db, run, record)
    db.query(Membership).filter_by(organization_id=org.id, user_id=actor.id).one().is_active = False
    db.flush()
    assert campaign_access.run_authorized(db, campaign, run)
    assert campaign_service.is_campaign_recipient_delivery_eligible(db, org.id, row.id)


def test_personal_delivery_stops_on_owner_deactivation_and_counts_skip(setup, db):
    org, owner, template, record = setup
    campaign = create(db, org, owner, template)
    run = enqueue(db, campaign, owner)
    row = recipient(db, run, record)
    db.query(Membership).filter_by(organization_id=org.id, user_id=owner.id).one().is_active = False
    db.flush()
    assert not campaign_service.is_campaign_recipient_delivery_eligible(db, org.id, row.id)
    assert row.status == "skipped" and row.skip_reason == "permission_revoked"
    assert run.skipped_count == 1


def test_personal_delivery_rechecks_assignment_after_materialization(setup, db):
    org, owner, template, record = setup
    campaign = create(db, org, owner, template)
    run = enqueue(db, campaign, owner)
    row = recipient(db, run, record)
    assert campaign_service.is_campaign_recipient_delivery_eligible(db, org.id, row.id)
    record.owner_id = uuid4()
    db.flush()
    assert not campaign_service.is_campaign_recipient_delivery_eligible(db, org.id, row.id)
    assert row.status == "skipped"


def test_campaign_snapshot_cannot_cross_organizations(setup, db):
    org, owner, template, record = setup
    campaign = create(db, org, owner, template, scope="org")
    run = enqueue(db, campaign, owner)
    row = recipient(db, run, record)
    run.authority_snapshot = {**run.authority_snapshot, "organization_id": str(uuid4())}
    db.flush()
    assert not campaign_service.is_campaign_recipient_delivery_eligible(db, org.id, row.id)


def test_publish_campaign_copies_personal_template_and_retains_credit(setup, db):
    org, owner, template, _ = setup
    template.scope, template.owner_user_id = "personal", owner.id
    db.flush()
    campaign = create(db, org, owner, template)
    published = campaign_access.publish_campaign(db, campaign, owner.id)
    copied_template = db.get(EmailTemplate, published.email_template_id)
    assert published.id != campaign.id and published.scope == "org"
    assert published.owner_user_id is None and published.status == "draft"
    assert published.scheduled_at is None and published.execution_authority is None
    assert published.proposed_by_user_id == owner.id
    assert copied_template.id != template.id and copied_template.scope == "org"
    template.body = "<p>Private edit</p>"
    assert copied_template.body == "<p>Hello</p>"


def test_publish_failure_rolls_back_template_copy(setup, db, monkeypatch):
    org, owner, template, _ = setup
    template.scope, template.owner_user_id = "personal", owner.id
    db.flush()
    campaign = create(db, org, owner, template)
    before = db.query(EmailTemplate).filter_by(organization_id=org.id).count()
    monkeypatch.setattr(
        campaign_service,
        "create_campaign",
        lambda *_a, **_kw: (_ for _ in ()).throw(ValueError("Publication failed")),
    )
    with pytest.raises(ValueError, match="Publication failed"):
        campaign_access.publish_campaign(db, campaign, owner.id)
    assert db.query(EmailTemplate).filter_by(organization_id=org.id).count() == before


@pytest.mark.asyncio
async def test_personal_campaign_create_and_publish_require_csrf(setup, db, authed_client):
    from app.core.csrf import CSRF_HEADER

    org, _, template, _ = setup
    response = await authed_client.post(
        "/campaigns",
        json={
            "name": "Personal via API",
            "scope": "personal",
            "email_template_id": str(template.id),
        },
    )
    assert response.status_code == 201
    assert response.json()["scope"] == "personal"
    campaign_id = response.json()["id"]
    token = authed_client.headers.pop(CSRF_HEADER)
    denied = await authed_client.post(f"/campaigns/{campaign_id}/publish")
    assert denied.status_code == 403
    authed_client.headers[CSRF_HEADER] = token
    published = await authed_client.post(f"/campaigns/{campaign_id}/publish")
    assert published.status_code == 200
    assert published.json()["scope"] == "org" and published.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_cross_org_campaign_is_not_accessible(setup, db, authed_client):
    _, owner, _, _ = setup
    other = Organization(id=uuid4(), name="Other", slug=f"other-{uuid4()}")
    db.add(other)
    db.flush()
    foreign_template = EmailTemplate(
        id=uuid4(),
        organization_id=other.id,
        name="Foreign template",
        subject="Hello",
        body="Hello",
        scope="org",
    )
    db.add(foreign_template)
    db.flush()
    foreign = Campaign(
        id=uuid4(),
        organization_id=other.id,
        name="Foreign",
        scope="org",
        email_template_id=foreign_template.id,
        recipient_type="case",
        filter_criteria={},
        status="draft",
        created_by_user_id=owner.id,
    )
    db.add(foreign)
    db.flush()
    response = await authed_client.get(f"/campaigns/{foreign.id}")
    assert response.status_code == 404
