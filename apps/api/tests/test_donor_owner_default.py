"""Donors created without an explicit owner wait in the org default queue."""

import pytest

from app.db.models import Queue
from app.services import queue_service


def test_meta_donor_without_owner_waits_in_default_queue(db, test_org):
    from app.services import meta_lead_service
    from tests.test_meta_donor_routing import _lead, _mapped_form

    form = _mapped_form(db, test_org.id, external_id="owner-default", lead_kind="egg_donor")
    lead = _lead(
        db,
        test_org.id,
        external_id="lead-owner-default",
        form_external_id=form.form_external_id,
        email="owner-default@example.com",
    )

    status, donor = meta_lead_service.process_stored_meta_lead(db, lead)

    assert status == "converted"
    default_queue = queue_service.get_or_create_default_queue(db, test_org.id)
    assert (donor.owner_type, donor.owner_id) == ("queue", default_queue.id)


@pytest.mark.asyncio
async def test_api_donor_create_defaults_owner_to_default_queue_and_keeps_explicit_owner(
    authed_client, db, test_org, test_user
):
    unowned = await authed_client.post(
        "/donors",
        json={"donor_type": "egg", "full_name": "Queue Donor", "email": "queue-donor@example.com"},
    )
    assert unowned.status_code == 201, unowned.text
    default_queue = db.query(Queue).filter(Queue.organization_id == test_org.id).one()
    assert default_queue.name == queue_service.DEFAULT_QUEUE_NAME
    assert unowned.json()["owner_type"] == "queue"
    assert unowned.json()["owner_id"] == str(default_queue.id)
    assert unowned.json()["owner_name"] == queue_service.DEFAULT_QUEUE_NAME

    owned = await authed_client.post(
        "/donors",
        json={
            "donor_type": "sperm",
            "full_name": "Owned Donor",
            "email": "owned-donor@example.com",
            "owner_type": "user",
            "owner_id": str(test_user.id),
        },
    )
    assert owned.status_code == 201, owned.text
    assert (owned.json()["owner_type"], owned.json()["owner_id"]) == ("user", str(test_user.id))
