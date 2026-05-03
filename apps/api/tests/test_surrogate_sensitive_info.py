import uuid

import pytest

from app.db.enums import SurrogateActivityType
from app.db.models import SurrogateActivityLog
from app.services import pipeline_service


async def _create_surrogate(authed_client, **overrides):
    payload = {
        "full_name": "Sensitive Info",
        "email": f"sensitive-{uuid.uuid4().hex[:8]}@example.com",
    }
    payload.update(overrides)
    response = await authed_client.post("/surrogates", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _set_stage(db, test_org, surrogate_id: str, stage_key: str):
    from app.db.models import Surrogate

    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, stage_key)
    assert stage is not None

    surrogate = db.get(Surrogate, uuid.UUID(surrogate_id))
    assert surrogate is not None
    surrogate.stage_id = stage.id
    surrogate.status_label = stage.label
    db.commit()


@pytest.mark.asyncio
async def test_sensitive_info_hidden_before_pending_docusign(authed_client):
    created = await _create_surrogate(
        authed_client,
        marital_status="Married",
        ssn="123-45-6789",
        address_line1="456 Surrogate Ave",
        address_line2="Unit 9",
        address_city="Dallas",
        address_state="TX",
        address_postal="75201",
        partner_name="Taylor Partner",
        partner_date_of_birth="1988-04-12",
        partner_email="partner@example.com",
        partner_phone="+15551234567",
        partner_ssn="987654321",
        partner_address_line1="123 Partner St",
        partner_city="Austin",
        partner_state="TX",
        partner_postal="78701",
    )

    detail_res = await authed_client.get(f"/surrogates/{created['id']}")
    assert detail_res.status_code == 200, detail_res.text
    payload = detail_res.json()

    assert payload["sensitive_info_available"] is False
    assert payload["marital_status"] is None
    assert payload["address_line1"] is None
    assert payload["partner_name"] is None
    assert payload["partner_date_of_birth"] is None
    assert payload["ssn_masked"] is None
    assert "ssn" not in payload
    assert "partner_ssn" not in payload

    reveal_res = await authed_client.post(f"/surrogates/{created['id']}/sensitive-info/reveal")
    assert reveal_res.status_code == 403


@pytest.mark.asyncio
async def test_sensitive_info_masked_and_revealable_after_pending_docusign(
    authed_client, db, test_org
):
    created = await _create_surrogate(
        authed_client,
        marital_status="Married",
        ssn="123456789",
        address_line1="456 Surrogate Ave",
        address_line2="Unit 9",
        address_city="Dallas",
        address_state="TX",
        address_postal="75201",
        partner_name="Taylor Partner",
        partner_date_of_birth="1988-04-12",
        partner_email="partner@example.com",
        partner_phone="+15551234567",
        partner_ssn="987-65-4321",
        partner_address_line1="123 Partner St",
        partner_address_line2="Apt 4",
        partner_city="Austin",
        partner_state="TX",
        partner_postal="78701",
    )
    _set_stage(db, test_org, created["id"], "pending_docusign")

    detail_res = await authed_client.get(f"/surrogates/{created['id']}")
    assert detail_res.status_code == 200, detail_res.text
    payload = detail_res.json()

    assert payload["sensitive_info_available"] is True
    assert payload["marital_status"] == "Married"
    assert payload["address_line1"] == "456 Surrogate Ave"
    assert payload["address_line2"] == "Unit 9"
    assert payload["address_city"] == "Dallas"
    assert payload["address_state"] == "TX"
    assert payload["address_postal"] == "75201"
    assert payload["partner_name"] == "Taylor Partner"
    assert payload["partner_date_of_birth"] == "1988-04-12"
    assert payload["partner_email"] == "partner@example.com"
    assert payload["partner_phone"] == "+15551234567"
    assert payload["partner_address_line1"] == "123 Partner St"
    assert payload["partner_state"] == "TX"
    assert payload["ssn_masked"] == "***-**-6789"
    assert payload["partner_ssn_masked"] == "***-**-4321"
    assert "ssn" not in payload
    assert "partner_ssn" not in payload

    reveal_res = await authed_client.post(f"/surrogates/{created['id']}/sensitive-info/reveal")
    assert reveal_res.status_code == 200, reveal_res.text
    revealed = reveal_res.json()
    assert revealed["ssn"] == "123-45-6789"
    assert revealed["partner_ssn"] == "987-65-4321"

    activity = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == uuid.UUID(created["id"]),
            SurrogateActivityLog.activity_type == SurrogateActivityType.SENSITIVE_INFO_REVEALED.value,
        )
        .one()
    )
    assert activity.details == {"fields": ["ssn", "partner_ssn"]}


@pytest.mark.asyncio
async def test_sensitive_info_updates_and_clears_address_and_partner_dob(
    authed_client, db, test_org
):
    created = await _create_surrogate(authed_client)
    _set_stage(db, test_org, created["id"], "pending_docusign")

    update_res = await authed_client.patch(
        f"/surrogates/{created['id']}",
        json={
            "address_line1": "11 Main St",
            "address_city": "Denver",
            "address_state": "CO",
            "address_postal": "80202",
            "partner_name": "Jordan Partner",
            "partner_date_of_birth": "1990-01-15",
            "partner_address_line1": "22 Partner Rd",
            "partner_city": "Boulder",
            "partner_state": "CO",
            "partner_postal": "80301",
        },
    )
    assert update_res.status_code == 200, update_res.text
    payload = update_res.json()
    assert payload["address_line1"] == "11 Main St"
    assert payload["address_city"] == "Denver"
    assert payload["address_state"] == "CO"
    assert payload["partner_date_of_birth"] == "1990-01-15"
    assert payload["partner_address_line1"] == "22 Partner Rd"

    clear_res = await authed_client.patch(
        f"/surrogates/{created['id']}",
        json={
            "address_line1": None,
            "address_city": None,
            "address_state": None,
            "address_postal": None,
            "partner_name": None,
            "partner_date_of_birth": None,
            "partner_address_line1": None,
            "partner_city": None,
            "partner_state": None,
            "partner_postal": None,
        },
    )
    assert clear_res.status_code == 200, clear_res.text
    cleared = clear_res.json()
    assert cleared["address_line1"] is None
    assert cleared["address_city"] is None
    assert cleared["partner_name"] is None
    assert cleared["partner_date_of_birth"] is None
    assert cleared["partner_address_line1"] is None


@pytest.mark.asyncio
async def test_sensitive_info_rejects_invalid_ssn(authed_client):
    created = await _create_surrogate(authed_client)

    response = await authed_client.patch(
        f"/surrogates/{created['id']}",
        json={"ssn": "12-345-6789"},
    )

    assert response.status_code == 422
