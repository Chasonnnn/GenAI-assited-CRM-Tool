from __future__ import annotations

import uuid

import pytest

from app.db.enums import Role
from app.db.models import Membership, User
from app.schemas.surrogate import SurrogateCreate
from app.services import email_service, email_template_draft_service, surrogate_service


def _create_member(db, org_id, *, role: Role = Role.CASE_MANAGER) -> tuple[User, Membership]:
    user = User(
        id=uuid.uuid4(),
        email=f"departing-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Departing User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=org_id,
        role=role,
    )
    db.add(membership)
    db.flush()
    return user, membership


@pytest.mark.asyncio
async def test_remove_member_deactivates_their_personal_template(
    authed_client, db, test_auth, test_org
):
    departing_user, membership = _create_member(db, test_org.id)
    template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=departing_user.id,
        name="Departing User Template",
        subject="Preserve this subject",
        body="<p>Preserve this body</p>",
        scope="personal",
        commit=False,
    )
    template_id = template.id
    departing_user_id = departing_user.id
    draft = email_template_draft_service.create_draft_from_template(
        db,
        template=template,
        user_id=departing_user.id,
    )
    draft_id = draft.id

    inactive_template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=departing_user.id,
        name="Already Inactive Personal Template",
        subject="Keep this version unchanged",
        body="<p>Already inactive</p>",
        scope="personal",
        commit=False,
    )
    email_service.update_template(
        db=db,
        template=inactive_template,
        user_id=departing_user.id,
        is_active=False,
        commit=False,
    )
    inactive_template_id = inactive_template.id
    inactive_template_version = inactive_template.current_version

    organization_template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=departing_user.id,
        name="Organization Template",
        subject="Keep organization template active",
        body="<p>Organization-owned</p>",
        scope="org",
        commit=False,
    )
    organization_template_id = organization_template.id

    other_user, _ = _create_member(db, test_org.id)
    other_template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=other_user.id,
        name="Other User Template",
        subject="Keep other personal template active",
        body="<p>Other user-owned</p>",
        scope="personal",
        commit=False,
    )
    other_template_id = other_template.id
    db.commit()

    response = await authed_client.delete(
        f"/settings/permissions/members/{membership.id}"
    )
    assert response.status_code == 200, response.text

    template_response = await authed_client.get(f"/email-templates/{template_id}")
    assert template_response.status_code == 200, template_response.text
    data = template_response.json()
    assert data["id"] == str(template_id)
    assert data["owner_user_id"] == str(departing_user_id)
    assert data["scope"] == "personal"
    assert data["subject"] == "Preserve this subject"
    assert data["body"] == "<p>Preserve this body</p>"
    assert data["is_active"] is False
    assert data["current_version"] == 2

    draft_response = await authed_client.get(f"/email-template-drafts/{draft_id}")
    assert draft_response.status_code == 200, draft_response.text
    draft_data = draft_response.json()
    assert draft_data["template_id"] == str(template_id)
    assert draft_data["body"] == "<p>Preserve this body</p>"
    assert draft_data["is_stale"] is True

    inactive_response = await authed_client.get(
        f"/email-templates/{inactive_template_id}"
    )
    assert inactive_response.status_code == 200, inactive_response.text
    assert inactive_response.json()["is_active"] is False
    assert inactive_response.json()["current_version"] == inactive_template_version

    organization_response = await authed_client.get(
        f"/email-templates/{organization_template_id}"
    )
    assert organization_response.status_code == 200, organization_response.text
    assert organization_response.json()["is_active"] is True

    other_template_response = await authed_client.get(
        f"/email-templates/{other_template_id}"
    )
    assert other_template_response.status_code == 200, other_template_response.text
    assert other_template_response.json()["is_active"] is True

    version_response = await authed_client.get(
        f"/email-templates/{template_id}/versions"
    )
    assert version_response.status_code == 200, version_response.text
    versions = version_response.json()
    assert versions[0]["version"] == 2
    assert versions[0]["created_by_user_id"] == str(test_auth.user.id)

    active_templates_response = await authed_client.get(
        "/email-templates?scope=personal&show_all_personal=true"
    )
    assert active_templates_response.status_code == 200
    assert template_id not in {
        uuid.UUID(item["id"]) for item in active_templates_response.json()
    }


@pytest.mark.asyncio
async def test_remove_member_releases_their_leads_to_unassigned_queue(
    authed_client, db, test_org
):
    departing_user, membership = _create_member(db, test_org.id)
    other_user, _ = _create_member(db, test_org.id)
    lead = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=departing_user.id,
        data=SurrogateCreate(
            full_name="Departing User Lead",
            email=f"departing-lead-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )
    lead_id = lead.id

    archived_lead = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=departing_user.id,
        data=SurrogateCreate(
            full_name="Archived Departing User Lead",
            email=f"archived-departing-lead-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )
    archived_lead.is_archived = True
    archived_lead_id = archived_lead.id

    other_user_lead = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=other_user.id,
        data=SurrogateCreate(
            full_name="Other User Lead",
            email=f"other-user-lead-{uuid.uuid4().hex[:8]}@example.com",
        ),
    )
    other_user_lead_id = other_user_lead.id

    queue_owned_lead = surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=departing_user.id,
        data=SurrogateCreate(
            full_name="Already Unassigned Lead",
            email=f"already-unassigned-{uuid.uuid4().hex[:8]}@example.com",
            assign_to_user=False,
        ),
    )
    queue_owned_lead_id = queue_owned_lead.id
    original_queue_id = queue_owned_lead.owner_id
    db.commit()

    response = await authed_client.delete(
        f"/settings/permissions/members/{membership.id}"
    )
    assert response.status_code == 200, response.text

    lead_response = await authed_client.get(f"/surrogates/{lead_id}")
    assert lead_response.status_code == 200, lead_response.text
    lead_data = lead_response.json()
    assert lead_data["owner_type"] == "queue"
    assert lead_data["owner_name"] == "Unassigned"

    db.expire_all()
    archived_lead = surrogate_service.get_surrogate(db, test_org.id, archived_lead_id)
    assert archived_lead is not None
    assert archived_lead.owner_type == "queue"
    assert archived_lead.assigned_at is None

    other_user_lead = surrogate_service.get_surrogate(db, test_org.id, other_user_lead_id)
    assert other_user_lead is not None
    assert other_user_lead.owner_type == "user"
    assert other_user_lead.owner_id == other_user.id

    queue_owned_lead = surrogate_service.get_surrogate(db, test_org.id, queue_owned_lead_id)
    assert queue_owned_lead is not None
    assert queue_owned_lead.owner_type == "queue"
    assert queue_owned_lead.owner_id == original_queue_id

    queue_response = await authed_client.get("/surrogates/unassigned-queue")
    assert queue_response.status_code == 200, queue_response.text
    assert lead_id in {uuid.UUID(item["id"]) for item in queue_response.json()["items"]}

    activity_response = await authed_client.get(f"/surrogates/{lead_id}/activity")
    assert activity_response.status_code == 200, activity_response.text
    release_events = [
        item
        for item in activity_response.json()["items"]
        if item["activity_type"] == "surrogate_released"
    ]
    assert len(release_events) == 1
    assert release_events[0]["details"]["from_user_id"] == str(departing_user.id)
    assert release_events[0]["details"]["reason"] == "owner_removed_from_organization"
