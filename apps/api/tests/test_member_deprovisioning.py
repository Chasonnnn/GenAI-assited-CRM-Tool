from __future__ import annotations

import uuid

import pytest

from app.db.enums import Role
from app.db.models import Membership, User
from app.schemas.surrogate import SurrogateCreate
from app.services import email_service, surrogate_service


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
