import uuid

import pytest

from app.db.models import IntendedParent


@pytest.mark.asyncio
async def test_intended_parent_detail_fields_round_trip(authed_client):
    create_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Jamie and Morgan Lee",
            "email": f"ip-detail-{uuid.uuid4().hex[:8]}@example.com",
            "date_of_birth": "1989-05-15",
            "partner_date_of_birth": "1991-08-09",
            "marital_status": "Married",
            "embryo_count": 4,
            "pgs_tested": True,
            "egg_source": "intended_mother",
            "sperm_source": "sperm_donor",
            "trust_provider_name": "North Star Trust",
            "trust_primary_contact_name": "Avery Chen",
            "trust_email": "contact@northstartrust.com",
            "trust_phone": "+15125550130",
            "trust_address_line1": "700 Trust Ave",
            "trust_address_line2": "Suite 200",
            "trust_city": "Austin",
            "trust_state": "tx",
            "trust_postal": "78703",
            "trust_case_reference": "NST-2049",
            "trust_funding_status": "funded",
            "trust_portal_url": "https://portal.northstartrust.com/cases/nst-2049",
            "trust_notes": "Monthly replenishment review.",
        },
    )
    assert create_res.status_code == 201, create_res.text
    ip_id = create_res.json()["id"]

    get_res = await authed_client.get(f"/intended-parents/{ip_id}")
    assert get_res.status_code == 200, get_res.text
    payload = get_res.json()

    assert payload["date_of_birth"] == "1989-05-15"
    assert payload["partner_date_of_birth"] == "1991-08-09"
    assert payload["marital_status"] == "Married"
    assert payload["embryo_count"] == 4
    assert payload["pgs_tested"] is True
    assert payload["egg_source"] == "intended_mother"
    assert payload["sperm_source"] == "sperm_donor"
    assert payload["trust_provider_name"] == "North Star Trust"
    assert payload["trust_primary_contact_name"] == "Avery Chen"
    assert payload["trust_email"] == "contact@northstartrust.com"
    assert payload["trust_phone"] == "+15125550130"
    assert payload["trust_address_line1"] == "700 Trust Ave"
    assert payload["trust_address_line2"] == "Suite 200"
    assert payload["trust_city"] == "Austin"
    assert payload["trust_state"] == "TX"
    assert payload["trust_postal"] == "78703"
    assert payload["trust_case_reference"] == "NST-2049"
    assert payload["trust_funding_status"] == "funded"
    assert payload["trust_portal_url"] == "https://portal.northstartrust.com/cases/nst-2049"
    assert payload["trust_notes"] == "Monthly replenishment review."


@pytest.mark.asyncio
async def test_intended_parent_patch_rejects_invalid_embryo_sources(authed_client):
    create_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Embryo Validation",
            "email": f"ip-embryo-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    ip_id = create_res.json()["id"]

    update_res = await authed_client.patch(
        f"/intended-parents/{ip_id}",
        json={"egg_source": "friend", "sperm_source": "unknown"},
    )
    assert update_res.status_code == 422, update_res.text


@pytest.mark.asyncio
async def test_intended_parent_patch_rejects_invalid_marital_status(authed_client):
    create_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Marital Validation",
            "email": f"ip-marital-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    ip_id = create_res.json()["id"]

    update_res = await authed_client.patch(
        f"/intended-parents/{ip_id}",
        json={"marital_status": "Complicated"},
    )
    assert update_res.status_code == 422, update_res.text


@pytest.mark.asyncio
async def test_intended_parent_patch_rejects_invalid_trust_funding_status(authed_client):
    create_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Trust Validation",
            "email": f"ip-trust-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    ip_id = create_res.json()["id"]

    update_res = await authed_client.patch(
        f"/intended-parents/{ip_id}",
        json={"trust_funding_status": "wire_sent"},
    )
    assert update_res.status_code == 422, update_res.text


@pytest.mark.asyncio
async def test_intended_parent_patch_can_clear_detail_and_ivf_fields(authed_client, db):
    create_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Taylor and Quinn Rivers",
            "email": f"ip-clear-{uuid.uuid4().hex[:8]}@example.com",
            "date_of_birth": "1988-01-02",
            "partner_date_of_birth": "1990-03-04",
            "marital_status": "Partnered",
            "embryo_count": 3,
            "pgs_tested": False,
            "egg_source": "egg_donor",
            "sperm_source": "intended_father",
            "ip_clinic_name": "RMA Austin",
            "ip_clinic_email": "clinic@example.com",
            "trust_provider_name": "Trust Co",
            "trust_primary_contact_name": "Jordan Escrow",
            "trust_email": "escrow@example.com",
            "trust_phone": "+15125550131",
            "trust_address_line1": "8 River Rd",
            "trust_city": "Austin",
            "trust_state": "TX",
            "trust_postal": "78704",
            "trust_case_reference": "TRUST-1",
            "trust_funding_status": "needs_replenishment",
            "trust_portal_url": "https://trust.example.com/cases/1",
            "trust_notes": "Awaiting replenishment.",
        },
    )
    assert create_res.status_code == 201, create_res.text
    ip_id = create_res.json()["id"]

    update_res = await authed_client.patch(
        f"/intended-parents/{ip_id}",
        json={
            "date_of_birth": None,
            "partner_date_of_birth": None,
            "marital_status": None,
            "embryo_count": None,
            "pgs_tested": None,
            "egg_source": None,
            "sperm_source": None,
            "ip_clinic_name": None,
            "ip_clinic_email": None,
            "trust_provider_name": None,
            "trust_primary_contact_name": None,
            "trust_email": None,
            "trust_phone": None,
            "trust_address_line1": None,
            "trust_address_line2": None,
            "trust_city": None,
            "trust_state": None,
            "trust_postal": None,
            "trust_case_reference": None,
            "trust_funding_status": None,
            "trust_portal_url": None,
            "trust_notes": None,
        },
    )
    assert update_res.status_code == 200, update_res.text
    payload = update_res.json()

    assert payload["date_of_birth"] is None
    assert payload["partner_date_of_birth"] is None
    assert payload["marital_status"] is None
    assert payload["embryo_count"] is None
    assert payload["pgs_tested"] is None
    assert payload["egg_source"] is None
    assert payload["sperm_source"] is None
    assert payload["ip_clinic_name"] is None
    assert payload["ip_clinic_email"] is None
    assert payload["trust_provider_name"] is None
    assert payload["trust_primary_contact_name"] is None
    assert payload["trust_email"] is None
    assert payload["trust_phone"] is None
    assert payload["trust_address_line1"] is None
    assert payload["trust_address_line2"] is None
    assert payload["trust_city"] is None
    assert payload["trust_state"] is None
    assert payload["trust_postal"] is None
    assert payload["trust_case_reference"] is None
    assert payload["trust_funding_status"] is None
    assert payload["trust_portal_url"] is None
    assert payload["trust_notes"] is None

    ip = db.query(IntendedParent).filter(IntendedParent.id == ip_id).one()
    assert ip.date_of_birth is None
    assert ip.partner_date_of_birth is None
    assert ip.marital_status is None
    assert ip.embryo_count is None
    assert ip.pgs_tested is None
    assert ip.egg_source is None
    assert ip.sperm_source is None
    assert ip.ip_clinic_name is None
    assert ip.ip_clinic_email is None
    assert ip.trust_provider_name is None
    assert ip.trust_primary_contact_name is None
    assert ip.trust_email is None
    assert ip.trust_phone is None
    assert ip.trust_address_line1 is None
    assert ip.trust_address_line2 is None
    assert ip.trust_city is None
    assert ip.trust_state is None
    assert ip.trust_postal is None
    assert ip.trust_case_reference is None
    assert ip.trust_funding_status is None
    assert ip.trust_portal_url is None
    assert ip.trust_notes is None
