import uuid

import pytest

from app.db.models import IntendedParent, Surrogate


@pytest.mark.asyncio
async def test_surrogate_contact_helpers_persist_on_create_and_update(
    authed_client, db, default_stage
):
    payload = {
        "full_name": "Alex Rivera",
        "email": f"alex.{uuid.uuid4().hex[:6]}@Example.COM",
        "phone": "5551234567",
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]

    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).one()
    assert surrogate.email_domain == "example.com"
    assert surrogate.phone_last4 == "4567"

    update_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}",
        json={"email": "ops+test@Support.IO", "phone": "5550001111"},
    )
    assert update_res.status_code == 200, update_res.text

    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).one()
    assert surrogate.email_domain == "support.io"
    assert surrogate.phone_last4 == "1111"

    clear_phone_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}",
        json={"phone": None},
    )
    assert clear_phone_res.status_code == 200, clear_phone_res.text

    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).one()
    assert surrogate.phone_last4 is None


@pytest.mark.asyncio
async def test_intended_parent_contact_helpers_persist_on_create_and_update(
    authed_client, db, test_org
):
    payload = {
        "full_name": "Casey Monroe",
        "email": f"casey.{uuid.uuid4().hex[:6]}@Mail.NET",
        "phone": "5559876543",
    }
    create_res = await authed_client.post("/intended-parents", json=payload)
    assert create_res.status_code == 201, create_res.text
    ip_id = create_res.json()["id"]

    ip = db.query(IntendedParent).filter(IntendedParent.id == ip_id).one()
    assert ip.email_domain == "mail.net"
    assert ip.phone_last4 == "6543"

    update_res = await authed_client.patch(
        f"/intended-parents/{ip_id}",
        json={"email": "new+ip@Example.ORG", "phone": "5552223333"},
    )
    assert update_res.status_code == 200, update_res.text

    ip = db.query(IntendedParent).filter(IntendedParent.id == ip_id).one()
    assert ip.email_domain == "example.org"
    assert ip.phone_last4 == "3333"
