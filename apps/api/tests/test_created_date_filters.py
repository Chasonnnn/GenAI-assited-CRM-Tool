import uuid
from datetime import datetime, timezone

import pytest

from app.db.models import IntendedParent, Surrogate


@pytest.mark.asyncio
async def test_surrogate_created_dates_endpoint_returns_distinct_context_dates(authed_client, db):
    first_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Alpha Lead",
            "email": f"alpha-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert first_res.status_code == 201, first_res.text
    first_id = first_res.json()["id"]

    second_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Beta Lead",
            "email": f"beta-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert second_res.status_code == 201, second_res.text
    second_id = second_res.json()["id"]

    third_res = await authed_client.post(
        "/surrogates",
        json={
            "full_name": "Beta Followup",
            "email": f"beta-followup-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert third_res.status_code == 201, third_res.text
    third_id = third_res.json()["id"]

    first_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(first_id)).first()
    second_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(second_id)).first()
    third_row = db.query(Surrogate).filter(Surrogate.id == uuid.UUID(third_id)).first()
    assert first_row is not None and second_row is not None and third_row is not None

    first_row.created_at = datetime(2026, 2, 16, 15, 0, tzinfo=timezone.utc)
    second_row.created_at = datetime(2026, 2, 18, 9, 30, tzinfo=timezone.utc)
    third_row.created_at = datetime(2026, 2, 18, 17, 45, tzinfo=timezone.utc)
    db.commit()

    all_dates_res = await authed_client.get("/surrogates/created-dates")
    assert all_dates_res.status_code == 200, all_dates_res.text
    assert all_dates_res.json() == ["2026-02-16", "2026-02-18"]

    q_filtered_res = await authed_client.get("/surrogates/created-dates", params={"q": "alpha"})
    assert q_filtered_res.status_code == 200, q_filtered_res.text
    assert q_filtered_res.json() == ["2026-02-16"]


@pytest.mark.asyncio
async def test_intended_parent_created_before_date_uses_created_at_day_boundary(authed_client, db):
    same_day_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Created Before Same Day",
            "email": f"ip-created-before-same-day-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert same_day_res.status_code == 201, same_day_res.text
    same_day_id = same_day_res.json()["id"]

    next_day_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Created Before Next Day",
            "email": f"ip-created-before-next-day-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert next_day_res.status_code == 201, next_day_res.text
    next_day_id = next_day_res.json()["id"]

    same_day_row = (
        db.query(IntendedParent).filter(IntendedParent.id == uuid.UUID(same_day_id)).first()
    )
    next_day_row = (
        db.query(IntendedParent).filter(IntendedParent.id == uuid.UUID(next_day_id)).first()
    )
    assert same_day_row is not None and next_day_row is not None

    same_day_row.created_at = datetime(2025, 1, 10, 13, 20, tzinfo=timezone.utc)
    next_day_row.created_at = datetime(2025, 1, 11, 0, 0, 1, tzinfo=timezone.utc)
    # Ensure created_before is not accidentally using updated_at
    next_day_row.updated_at = datetime(2025, 1, 10, 16, 0, tzinfo=timezone.utc)
    db.commit()

    list_res = await authed_client.get("/intended-parents", params={"created_before": "2025-01-10"})
    assert list_res.status_code == 200, list_res.text
    ids = {item["id"] for item in list_res.json()["items"]}

    assert same_day_id in ids
    assert next_day_id not in ids


@pytest.mark.asyncio
async def test_intended_parent_created_dates_endpoint_returns_distinct_context_dates(
    authed_client, db
):
    alpha_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Alpha Parent",
            "email": f"ip-alpha-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert alpha_res.status_code == 201, alpha_res.text
    alpha_id = alpha_res.json()["id"]

    beta_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Beta Parent",
            "email": f"ip-beta-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert beta_res.status_code == 201, beta_res.text
    beta_id = beta_res.json()["id"]

    beta_two_res = await authed_client.post(
        "/intended-parents",
        json={
            "full_name": "Beta Parent Second",
            "email": f"ip-beta-second-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    assert beta_two_res.status_code == 201, beta_two_res.text
    beta_two_id = beta_two_res.json()["id"]

    alpha_row = db.query(IntendedParent).filter(IntendedParent.id == uuid.UUID(alpha_id)).first()
    beta_row = db.query(IntendedParent).filter(IntendedParent.id == uuid.UUID(beta_id)).first()
    beta_two_row = (
        db.query(IntendedParent).filter(IntendedParent.id == uuid.UUID(beta_two_id)).first()
    )
    assert alpha_row is not None and beta_row is not None and beta_two_row is not None

    alpha_row.created_at = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
    beta_row.created_at = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)
    beta_two_row.created_at = datetime(2026, 2, 18, 16, 30, tzinfo=timezone.utc)
    db.commit()

    all_dates_res = await authed_client.get("/intended-parents/created-dates")
    assert all_dates_res.status_code == 200, all_dates_res.text
    assert all_dates_res.json() == ["2026-02-16", "2026-02-18"]

    q_filtered_res = await authed_client.get(
        "/intended-parents/created-dates", params={"q": "alpha"}
    )
    assert q_filtered_res.status_code == 200, q_filtered_res.text
    assert q_filtered_res.json() == ["2026-02-16"]
