import uuid

import pytest


@pytest.mark.asyncio
async def test_create_surrogate_with_medical_fields_roundtrip(authed_client):
    payload = {
        "full_name": "Medical Intake",
        "email": f"medical-{uuid.uuid4().hex[:8]}@example.com",
        "insurance_company": "Acme Health",
        "insurance_plan_name": "Gold Plus",
        "insurance_phone": "+15551234567",
        "insurance_policy_number": "POL-12345",
        "insurance_member_id": "MEM-67890",
        "insurance_group_number": "GRP-42",
        "insurance_subscriber_name": "Primary Subscriber",
        "insurance_subscriber_dob": "1985-03-15",
        "clinic_name": "City IVF",
        "clinic_address_line1": "123 Main St",
        "clinic_city": "Austin",
        "clinic_state": "TX",
        "clinic_postal": "78701",
        "clinic_phone": "+15125550123",
        "clinic_email": "intake@cityivf.com",
        "delivery_hospital_name": "St. Luke's",
        "delivery_hospital_email": "labor@stlukes.com",
        "pregnancy_start_date": "2025-01-10",
        "pregnancy_due_date": "2025-10-17",
    }

    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()

    assert created["insurance_company"] == payload["insurance_company"]
    assert created["insurance_plan_name"] == payload["insurance_plan_name"]
    assert created["insurance_member_id"] == payload["insurance_member_id"]
    assert created["clinic_name"] == payload["clinic_name"]
    assert created["clinic_address_line1"] == payload["clinic_address_line1"]
    assert created["clinic_city"] == payload["clinic_city"]
    assert created["clinic_state"] == payload["clinic_state"]
    assert created["clinic_postal"] == payload["clinic_postal"]
    assert created["clinic_email"] == payload["clinic_email"]
    assert created["delivery_hospital_name"] == payload["delivery_hospital_name"]
    assert created["delivery_hospital_email"] == payload["delivery_hospital_email"]
    assert created["pregnancy_start_date"] == payload["pregnancy_start_date"]
    assert created["pregnancy_due_date"] == payload["pregnancy_due_date"]

    get_res = await authed_client.get(f"/surrogates/{created['id']}")
    assert get_res.status_code == 200, get_res.text
    fetched = get_res.json()

    assert fetched["insurance_company"] == payload["insurance_company"]
    assert fetched["clinic_name"] == payload["clinic_name"]
    assert fetched["delivery_hospital_email"] == payload["delivery_hospital_email"]
    assert fetched["pregnancy_start_date"] == payload["pregnancy_start_date"]
    assert fetched["pregnancy_due_date"] == payload["pregnancy_due_date"]


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
        f"/surrogates/{surrogate_id}",
        json={
            "clinic_name": "Austin Fertility",
            "insurance_company": "Guardian Health",
            "pregnancy_start_date": "2025-02-01",
        },
    )
    assert patch_res.status_code == 200, patch_res.text

    activity_res = await authed_client.get(f"/surrogates/{surrogate_id}/activity")
    assert activity_res.status_code == 200, activity_res.text
    activity_types = {item["activity_type"] for item in activity_res.json()["items"]}

    assert "medical_info_updated" in activity_types
    assert "insurance_info_updated" in activity_types
    assert "pregnancy_dates_updated" in activity_types
