import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy import update as sql_update

from app.db.models import EmailLog, Form, FormSubmission, MetaLead, Surrogate, SurrogateActivityLog
from app.db.enums import SurrogateActivityType


@pytest.mark.asyncio
async def test_surrogates_list_includes_race(authed_client):
    payload = {
        "full_name": "Race Test",
        "email": f"race-{uuid.uuid4().hex[:8]}@example.com",
        "race": "Asian",
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]

    match = next((item for item in items if item["id"] == created_id), None)
    assert match is not None
    assert match["race"] == payload["race"]
    assert match["last_activity_at"] is not None


@pytest.mark.asyncio
async def test_surrogates_list_normalizes_bmi_using_rounded_inches(authed_client):
    payload = {
        "full_name": "BMI Test",
        "email": f"bmi-{uuid.uuid4().hex[:8]}@example.com",
        "height_ft": 5.1,
        "weight_lb": 180,
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]
    match = next((item for item in items if item["id"] == created_id), None)

    assert match is not None
    assert match["bmi"] == pytest.approx(34.0, abs=0.01)


@pytest.mark.asyncio
async def test_surrogates_list_does_not_fallback_to_updated_at_for_last_activity(authed_client, db):
    payload = {
        "full_name": "No Activity Test",
        "email": f"no-activity-{uuid.uuid4().hex[:8]}@example.com",
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]
    surrogate_id = uuid.UUID(created_id)

    db.query(SurrogateActivityLog).filter(
        SurrogateActivityLog.surrogate_id == surrogate_id
    ).delete()
    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate is not None
    surrogate.updated_at = datetime.now(timezone.utc)
    db.commit()

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]
    match = next((item for item in items if item["id"] == created_id), None)

    assert match is not None
    assert match["last_activity_at"] is None


@pytest.mark.asyncio
async def test_surrogates_list_includes_updated_at(authed_client):
    payload = {
        "full_name": "Updated At Test",
        "email": f"updated-at-{uuid.uuid4().hex[:8]}@example.com",
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    match = next((item for item in list_res.json()["items"] if item["id"] == created_id), None)

    assert match is not None
    assert match["updated_at"] is not None


@pytest.mark.asyncio
async def test_surrogates_list_supports_updated_at_sorting(authed_client, db):
    first_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Updated Sort First",
            "email": f"updated-sort-first-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert first_res.status_code == 201, first_res.text
    first_id = first_res.json()["id"]

    second_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Updated Sort Second",
            "email": f"updated-sort-second-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert second_res.status_code == 201, second_res.text
    second_id = second_res.json()["id"]

    first_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(first_id)).first()
    second_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(second_id)).first()
    assert first_row is not None and second_row is not None

    first_updated_at = datetime(2030, 1, 2, 9, 0, tzinfo=timezone.utc)
    second_updated_at = datetime(2030, 1, 3, 9, 0, tzinfo=timezone.utc)

    db.execute(text("ALTER TABLE surrogates DISABLE TRIGGER ALL"))
    try:
        db.execute(
            sql_update(Surrogate)
            .where(Surrogate.id == uuid.UUID(first_id))
            .values(full_name="Updated Sort First Edited", updated_at=first_updated_at)
        )
        db.execute(
            sql_update(Surrogate)
            .where(Surrogate.id == uuid.UUID(second_id))
            .values(full_name="Updated Sort Second Edited", updated_at=second_updated_at)
        )
        db.commit()
    finally:
        db.execute(text("ALTER TABLE surrogates ENABLE TRIGGER ALL"))
        db.commit()

    db.refresh(first_row)
    db.refresh(second_row)

    assert first_row.updated_at == first_updated_at
    assert second_row.updated_at == second_updated_at
    assert second_row.updated_at > first_row.updated_at

    desc_res = await authed_client.get(
        "/surrogates",
        params={"sort_by": "updated_at", "sort_order": "desc"},
    )
    assert desc_res.status_code == 200, desc_res.text
    desc_ids = [item["id"] for item in desc_res.json()["items"]]
    assert desc_ids.index(second_id) < desc_ids.index(first_id)

    asc_res = await authed_client.get(
        "/surrogates",
        params={"sort_by": "updated_at", "sort_order": "asc"},
    )
    assert asc_res.status_code == 200, asc_res.text
    asc_ids = [item["id"] for item in asc_res.json()["items"]]
    assert asc_ids.index(first_id) < asc_ids.index(second_id)


@pytest.mark.asyncio
async def test_surrogates_list_supports_last_modified_sorting(authed_client, db, test_org):
    first_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Last Modified First",
            "email": f"last-modified-first-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert first_res.status_code == 201, first_res.text
    first_id = first_res.json()["id"]

    second_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Last Modified Second",
            "email": f"last-modified-second-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert second_res.status_code == 201, second_res.text
    second_id = second_res.json()["id"]

    first_updated_at = datetime(2030, 1, 2, 9, 0, tzinfo=timezone.utc)
    second_updated_at = datetime(2030, 1, 3, 9, 0, tzinfo=timezone.utc)
    first_activity_at = datetime(2030, 1, 4, 9, 0, tzinfo=timezone.utc)

    db.execute(text("ALTER TABLE surrogates DISABLE TRIGGER ALL"))
    try:
        db.execute(
            sql_update(Surrogate)
            .where(Surrogate.id == uuid.UUID(first_id))
            .values(updated_at=first_updated_at)
        )
        db.execute(
            sql_update(Surrogate)
            .where(Surrogate.id == uuid.UUID(second_id))
            .values(updated_at=second_updated_at)
        )
        db.commit()
    finally:
        db.execute(text("ALTER TABLE surrogates ENABLE TRIGGER ALL"))
        db.commit()

    db.add(
        SurrogateActivityLog(
            organization_id=test_org.id,
            surrogate_id=uuid.UUID(first_id),
            activity_type=SurrogateActivityType.CONTACT_ATTEMPT.value,
            actor_user_id=None,
            details={"source": "test"},
            created_at=first_activity_at,
        )
    )
    db.commit()

    desc_res = await authed_client.get(
        "/surrogates",
        params={"sort_by": "last_modified_at", "sort_order": "desc"},
    )
    assert desc_res.status_code == 200, desc_res.text
    desc_ids = [item["id"] for item in desc_res.json()["items"]]
    assert desc_ids.index(first_id) < desc_ids.index(second_id)

    asc_res = await authed_client.get(
        "/surrogates",
        params={"sort_by": "last_modified_at", "sort_order": "asc"},
    )
    assert asc_res.status_code == 200, asc_res.text
    asc_ids = [item["id"] for item in asc_res.json()["items"]]
    assert asc_ids.index(second_id) < asc_ids.index(first_id)


@pytest.mark.asyncio
async def test_surrogates_list_filters_priority_only(authed_client):
    priority_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Priority Lead",
            "email": f"priority-lead-{uuid.uuid4().hex[:8]}@example.com",
            "is_priority": True,
        },
    )
    assert priority_res.status_code == 201, priority_res.text
    priority_id = priority_res.json()["id"]

    normal_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Normal Lead",
            "email": f"normal-lead-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert normal_res.status_code == 201, normal_res.text
    normal_id = normal_res.json()["id"]

    list_res = await authed_client.get("/surrogates", params={"is_priority": "true"})
    assert list_res.status_code == 200, list_res.text
    ids = {item["id"] for item in list_res.json()["items"]}

    assert priority_id in ids
    assert normal_id not in ids


@pytest.mark.asyncio
async def test_surrogate_created_dates_filters_priority_only(authed_client, db):
    priority_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Priority Created Date",
            "email": f"priority-created-{uuid.uuid4().hex[:8]}@example.com",
            "is_priority": True,
        },
    )
    assert priority_res.status_code == 201, priority_res.text
    priority_id = priority_res.json()["id"]

    normal_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Normal Created Date",
            "email": f"normal-created-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert normal_res.status_code == 201, normal_res.text
    normal_id = normal_res.json()["id"]

    priority_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(priority_id)).first()
    normal_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(normal_id)).first()
    assert priority_row is not None and normal_row is not None

    priority_row.created_at = datetime(2025, 1, 10, 12, 0, tzinfo=timezone.utc)
    normal_row.created_at = datetime(2025, 1, 11, 12, 0, tzinfo=timezone.utc)
    db.commit()

    dates_res = await authed_client.get("/surrogates/created-dates", params={"is_priority": "true"})
    assert dates_res.status_code == 200, dates_res.text
    assert dates_res.json() == ["2025-01-10"]


@pytest.mark.asyncio
async def test_surrogates_list_created_to_date_includes_entire_day(authed_client, db):
    res_same_day = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Created To Same Day",
            "email": f"created-to-same-day-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert res_same_day.status_code == 201, res_same_day.text
    same_day_id = res_same_day.json()["id"]

    res_next_day = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Created To Next Day",
            "email": f"created-to-next-day-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert res_next_day.status_code == 201, res_next_day.text
    next_day_id = res_next_day.json()["id"]

    same_day_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(same_day_id)).first()
    next_day_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(next_day_id)).first()
    assert same_day_row is not None and next_day_row is not None

    same_day_row.created_at = datetime(2025, 1, 10, 15, 45, tzinfo=timezone.utc)
    next_day_row.created_at = datetime(2025, 1, 11, 0, 0, 1, tzinfo=timezone.utc)
    db.commit()

    list_res = await authed_client.get("/surrogates", params={"created_to": "2025-01-10"})
    assert list_res.status_code == 200, list_res.text
    ids = {item["id"] for item in list_res.json()["items"]}

    assert same_day_id in ids
    assert next_day_id not in ids


@pytest.mark.asyncio
async def test_surrogate_list_and_detail_include_stage_key_fields(authed_client):
    payload = {
        "full_name": "Stage Key Contract",
        "email": f"stage-key-{uuid.uuid4().hex[:8]}@example.com",
    }
    create_res = await authed_client.post("/surrogates", json=payload)
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]

    list_res = await authed_client.get("/surrogates")
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()["items"]
    match = next((item for item in items if item["id"] == created_id), None)

    assert match is not None
    assert match["stage_key"] == "new_unread"

    detail_res = await authed_client.get(f"/surrogates/{created_id}")
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()

    assert detail["stage_key"] == "new_unread"
    assert detail["stage_slug"] == "new_unread"
    assert detail["stage_type"] == "intake"
    assert detail["paused_from_stage_key"] is None


@pytest.mark.asyncio
async def test_surrogate_detail_includes_lead_intake_warnings_with_raw_values(
    authed_client, db, test_org
):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Lead Review",
            "email": f"lead-review-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = uuid.UUID(create_res.json()["id"])

    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate is not None
    surrogate.email = "broken-email"
    surrogate.phone = None
    surrogate.state = None
    surrogate.height_ft = None
    surrogate.weight_lb = None

    form = Form(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Lead Intake Review",
    )
    db.add(form)
    db.flush()

    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form_id=form.id,
        surrogate_id=surrogate.id,
        source_mode="shared",
        answers_json={
            "email": "broken-email",
            "phone": "555-CALL-NOW",
            "state": "Atlantis",
            "height": "5 ft 7 in",
            "weight_lb": "140 lbs",
        },
    )
    db.add(submission)
    db.commit()

    detail_res = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()

    assert detail["lead_intake_warnings"] == [
        {
            "field_key": "email",
            "issue": "invalid_value",
            "raw_value": "broken-email",
        },
        {
            "field_key": "phone",
            "issue": "missing_value",
            "raw_value": "555-CALL-NOW",
        },
        {
            "field_key": "state",
            "issue": "missing_value",
            "raw_value": "Atlantis",
        },
        {
            "field_key": "height_ft",
            "issue": "missing_value",
            "raw_value": "5 ft 7 in",
        },
        {
            "field_key": "weight_lb",
            "issue": "missing_value",
            "raw_value": "140 lbs",
        },
    ]


@pytest.mark.asyncio
async def test_surrogate_detail_falls_back_to_meta_raw_field_data_for_lead_intake_warnings(
    authed_client, db, test_org
):
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Meta Lead Review",
            "email": f"meta-lead-review-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = uuid.UUID(create_res.json()["id"])

    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate is not None
    surrogate.phone = None
    surrogate.state = None
    surrogate.height_ft = None
    surrogate.weight_lb = None

    meta_lead = MetaLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        meta_lead_id=f"lead-{uuid.uuid4().hex[:8]}",
        raw_payload={
            "field_data": [
                {"name": "Phone Number", "values": ["555-CALL-NOW"]},
                {"name": "State", "values": ["Atlantis"]},
                {"name": "Height", "values": ["5 ft 7 in"]},
                {"name": "Weight", "values": ["140 lbs"]},
            ]
        },
    )
    db.add(meta_lead)
    db.flush()

    surrogate.meta_lead_id = meta_lead.id
    db.commit()

    detail_res = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()

    assert detail["lead_intake_warnings"] == [
        {
            "field_key": "phone",
            "issue": "missing_value",
            "raw_value": "555-CALL-NOW",
        },
        {
            "field_key": "state",
            "issue": "missing_value",
            "raw_value": "Atlantis",
        },
        {
            "field_key": "height_ft",
            "issue": "missing_value",
            "raw_value": "5 ft 7 in",
        },
        {
            "field_key": "weight_lb",
            "issue": "missing_value",
            "raw_value": "140 lbs",
        },
    ]


@pytest.mark.asyncio
async def test_surrogate_detail_flags_bounced_email_from_resend_activity(
    authed_client, db, test_org
):
    bounced_email = f"lead-bounced-{uuid.uuid4().hex[:8]}@example.com"
    create_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Lead Bounced",
            "email": bounced_email,
        },
    )
    assert create_res.status_code == 201, create_res.text
    surrogate_id = uuid.UUID(create_res.json()["id"])

    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate is not None

    form = Form(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        name="Lead Intake Review",
    )
    db.add(form)
    db.flush()

    submission = FormSubmission(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        form_id=form.id,
        surrogate_id=surrogate.id,
        source_mode="shared",
        answers_json={
            "email": bounced_email,
        },
    )
    db.add(submission)

    email_log = EmailLog(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_id=surrogate.id,
        recipient_email=bounced_email,
        subject="Test bounced email",
        body="Body",
        resend_status="bounced",
        bounced_at=datetime.now(timezone.utc),
        error="bounced",
    )
    db.add(email_log)
    db.flush()

    db.add(
        SurrogateActivityLog(
            id=uuid.uuid4(),
            surrogate_id=surrogate.id,
            organization_id=test_org.id,
            activity_type="email_bounced",
            actor_user_id=None,
            details={
                "email_log_id": str(email_log.id),
                "provider": "resend",
                "reason": "bounced",
            },
        )
    )
    db.commit()

    detail_res = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()

    assert detail["lead_intake_warnings"] == [
        {
            "field_key": "email",
            "issue": "invalid_value",
            "raw_value": bounced_email,
        },
    ]
