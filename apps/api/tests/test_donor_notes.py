import uuid

import pytest

from app.core.encryption import hash_email
from app.db.models import Donor, Organization


async def _create_donor(client) -> dict:
    response = await client.post(
        "/donors",
        json={
            "donor_type": "sperm",
            "full_name": "Notes Donor",
            "email": f"notes-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_donor_notes_create_list_sanitize_and_delete(authed_client):
    donor = await _create_donor(authed_client)

    created = await authed_client.post(
        f"/donors/{donor['id']}/notes",
        json={"content": "<p>Cleared screening</p><script>alert('x')</script>"},
    )
    assert created.status_code == 201, created.text
    note = created.json()
    assert note["entity_type"] == "donor"
    assert note["entity_id"] == donor["id"]
    assert "<script" not in note["content"]

    listed = await authed_client.get(f"/donors/{donor['id']}/notes")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [note["id"]]

    deleted = await authed_client.delete(f"/donors/{donor['id']}/notes/{note['id']}")
    assert deleted.status_code == 204
    assert (await authed_client.get(f"/donors/{donor['id']}/notes")).json() == []


@pytest.mark.asyncio
async def test_donor_notes_are_organization_scoped(authed_client, db, default_stage):
    foreign_org = Organization(
        id=uuid.uuid4(),
        name="Foreign Donor Notes",
        slug=f"foreign-donor-notes-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(foreign_org)
    db.flush()
    email = "foreign-notes@example.com"
    foreign = Donor(
        id=uuid.uuid4(),
        organization_id=foreign_org.id,
        donor_number="D10001",
        donor_type="egg",
        full_name="Foreign Notes Donor",
        email=email,
        email_hash=hash_email(email),
        stage_id=default_stage.id,
    )
    db.add(foreign)
    db.flush()

    listed = await authed_client.get(f"/donors/{foreign.id}/notes")
    assert listed.status_code == 404
    created = await authed_client.post(
        f"/donors/{foreign.id}/notes",
        json={"content": "Must not cross organizations"},
    )
    assert created.status_code == 404
