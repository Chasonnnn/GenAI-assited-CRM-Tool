import uuid
from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_surrogate_payloads_reject_flat_medical_fields(authed_client):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Medical Intake",
            "email": f"medical-{uuid.uuid4().hex[:8]}@example.com",
            "insurance_company": "Acme Health",
            "clinic_name": "City IVF",
        },
    )
    assert create_res.status_code == 422, create_res.text
    assert "clinic_name, insurance_company" in create_res.text

    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Medical Intake",
            "email": f"medical-{uuid.uuid4().hex[:8]}@example.com",
            "embryo_stage": "day_5",
            "pregnancy_start_date": "2025-01-10",
        },
    )
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()
    assert "clinic_name" not in created and "insurance_company" not in created
    assert created["embryo_stage"] == "day_5"

    patch_res = await authed_client.patch(
        f"/surrogates/{created['id']}", json={"ob_provider_name": "Dr. Betty OB"}
    )
    assert patch_res.status_code == 422, patch_res.text


@pytest.mark.asyncio
async def test_update_surrogate_accepts_only_canonical_embryo_stage_options(authed_client):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Embryo Stage",
            "email": f"embryo-stage-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]

    patch_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}",
        json={"embryo_stage": "day_6"},
    )
    assert patch_res.status_code == 200, patch_res.text
    assert patch_res.json()["embryo_stage"] == "day_6"

    invalid_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}",
        json={"embryo_stage": "blastocyst"},
    )
    assert invalid_res.status_code == 422, invalid_res.text


@pytest.mark.asyncio
async def test_update_surrogate_logs_medical_insurance_pregnancy_activity(authed_client):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Activity Log",
            "email": f"activity-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = create_res.json()["id"]

    patch_res = await authed_client.patch(
        f"/surrogates/{surrogate_id}", json={"pregnancy_start_date": "2025-02-01"}
    )
    assert patch_res.status_code == 200, patch_res.text
    for section, name in (("clinic", "Austin Fertility"), ("insurance", "Guardian Health")):
        record_res = await authed_client.post(
            f"/surrogates/{surrogate_id}/medical-records",
            json={"section": section, "effective_date": "2025-02-01", "name": name},
        )
        assert record_res.status_code == 200, record_res.text

    activity_res = await authed_client.get(f"/surrogates/{surrogate_id}/activity")
    assert activity_res.status_code == 200, activity_res.text
    activity_types = {item["activity_type"] for item in activity_res.json()["items"]}

    assert "medical_info_updated" in activity_types
    assert "insurance_info_updated" in activity_types
    assert "pregnancy_dates_updated" in activity_types


@pytest.mark.asyncio
async def test_create_surrogate_canonicalizes_numeric_height_to_nearest_inch(authed_client):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Canonical Height",
            "email": f"canonical-height-{uuid.uuid4().hex[:8]}@example.com",
            "height_ft": 4.8,
            "weight_lb": 120,
        },
    )
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()

    assert Decimal(created["height_ft"]) == Decimal("4.83")

    get_res = await authed_client.get(f"/surrogates/{created['id']}")
    assert get_res.status_code == 200, get_res.text
    fetched = get_res.json()

    assert Decimal(fetched["height_ft"]) == Decimal("4.83")
