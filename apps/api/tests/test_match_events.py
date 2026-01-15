"""
Tests for Match Events endpoints.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.encryption import hash_email
from app.db.models import Surrogate, IntendedParent, Match
from app.utils.normalization import normalize_email


def _create_case(db, org_id, user_id, stage):
    email = f"case-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    case = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Test Case",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(case)
    db.flush()
    return case


def _create_intended_parent(db, org_id):
    email = f"ip-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    ip = IntendedParent(
        id=uuid.uuid4(),
        organization_id=org_id,
        intended_parent_number=f"I{uuid.uuid4().int % 90000 + 10000:05d}",
        full_name="Test IP",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(ip)
    db.flush()
    return ip


def _create_match(db, org_id, user_id, stage):
    case = _create_case(db, org_id, user_id, stage)
    ip = _create_intended_parent(db, org_id)
    match = Match(
        id=uuid.uuid4(),
        organization_id=org_id,
        match_number=f"M{uuid.uuid4().int % 90000 + 10000:05d}",
        surrogate_id=case.id,
        intended_parent_id=ip.id,
        proposed_by_user_id=user_id,
    )
    db.add(match)
    db.flush()
    return match


@pytest.mark.asyncio
async def test_create_all_day_requires_start_date(
    authed_client: AsyncClient, db, test_org, test_user, default_stage
):
    match = _create_match(db, test_org.id, test_user.id, default_stage)

    response = await authed_client.post(
        f"/matches/{match.id}/events",
        json={
            "person_type": "surrogate",
            "event_type": "medical_exam",
            "title": "Exam",
            "all_day": True,
        },
    )

    assert response.status_code == 400
    assert "start_date" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_timed_requires_start_time(
    authed_client: AsyncClient, db, test_org, test_user, default_stage
):
    match = _create_match(db, test_org.id, test_user.id, default_stage)

    response = await authed_client.post(
        f"/matches/{match.id}/events",
        json={
            "person_type": "ip",
            "event_type": "legal",
            "title": "Legal meeting",
        },
    )

    assert response.status_code == 400
    assert "starts_at" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_timed_rejects_invalid_end_time(
    authed_client: AsyncClient, db, test_org, test_user, default_stage
):
    match = _create_match(db, test_org.id, test_user.id, default_stage)

    response = await authed_client.post(
        f"/matches/{match.id}/events",
        json={
            "person_type": "ip",
            "event_type": "custom",
            "title": "Timed event",
            "starts_at": "2024-05-01T10:00:00Z",
            "ends_at": "2024-05-01T09:00:00Z",
        },
    )

    assert response.status_code == 400
    assert "ends_at" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_events_includes_overlapping_all_day(
    authed_client: AsyncClient, db, test_org, test_user, default_stage
):
    match = _create_match(db, test_org.id, test_user.id, default_stage)

    create_response = await authed_client.post(
        f"/matches/{match.id}/events",
        json={
            "person_type": "surrogate",
            "event_type": "delivery",
            "title": "Delivery window",
            "all_day": True,
            "start_date": "2024-05-01",
            "end_date": "2024-05-03",
        },
    )
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    list_response = await authed_client.get(
        f"/matches/{match.id}/events",
        params={"from_date": "2024-05-02", "to_date": "2024-05-02"},
    )
    assert list_response.status_code == 200
    events = list_response.json()

    assert any(event["id"] == created_id for event in events)


@pytest.mark.asyncio
async def test_list_events_includes_timed_in_range(
    authed_client: AsyncClient, db, test_org, test_user, default_stage
):
    match = _create_match(db, test_org.id, test_user.id, default_stage)

    create_response = await authed_client.post(
        f"/matches/{match.id}/events",
        json={
            "person_type": "ip",
            "event_type": "custom",
            "title": "Timed check-in",
            "starts_at": "2024-05-02T12:00:00Z",
            "ends_at": "2024-05-02T13:00:00Z",
        },
    )
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    list_response = await authed_client.get(
        f"/matches/{match.id}/events",
        params={"from_date": "2024-05-02", "to_date": "2024-05-02"},
    )
    assert list_response.status_code == 200
    events = list_response.json()

    assert any(event["id"] == created_id for event in events)


@pytest.mark.asyncio
async def test_update_all_day_rejects_invalid_date_range(
    authed_client: AsyncClient, db, test_org, test_user, default_stage
):
    match = _create_match(db, test_org.id, test_user.id, default_stage)

    create_response = await authed_client.post(
        f"/matches/{match.id}/events",
        json={
            "person_type": "surrogate",
            "event_type": "medical_exam",
            "title": "Lab window",
            "all_day": True,
            "start_date": "2024-06-10",
            "end_date": "2024-06-11",
        },
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    update_response = await authed_client.put(
        f"/matches/{match.id}/events/{event_id}",
        json={
            "end_date": "2024-06-09",
        },
    )

    assert update_response.status_code == 400
    assert "end_date" in update_response.json()["detail"]


@pytest.mark.asyncio
async def test_update_timed_to_all_day_clears_times(
    authed_client: AsyncClient, db, test_org, test_user, default_stage
):
    match = _create_match(db, test_org.id, test_user.id, default_stage)

    create_response = await authed_client.post(
        f"/matches/{match.id}/events",
        json={
            "person_type": "surrogate",
            "event_type": "medical_exam",
            "title": "Timed event",
            "starts_at": "2024-06-01T10:00:00Z",
            "ends_at": "2024-06-01T11:00:00Z",
        },
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    update_response = await authed_client.put(
        f"/matches/{match.id}/events/{event_id}",
        json={
            "all_day": True,
            "start_date": "2024-06-01",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["all_day"] is True
    assert updated["start_date"] == "2024-06-01"
    assert updated["starts_at"] is None
    assert updated["ends_at"] is None


@pytest.mark.asyncio
async def test_update_all_day_to_timed_clears_dates(
    authed_client: AsyncClient, db, test_org, test_user, default_stage
):
    match = _create_match(db, test_org.id, test_user.id, default_stage)

    create_response = await authed_client.post(
        f"/matches/{match.id}/events",
        json={
            "person_type": "surrogate",
            "event_type": "legal",
            "title": "All-day event",
            "all_day": True,
            "start_date": "2024-07-01",
            "end_date": "2024-07-02",
        },
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    update_response = await authed_client.put(
        f"/matches/{match.id}/events/{event_id}",
        json={
            "all_day": False,
            "starts_at": "2024-07-01T09:00:00Z",
            "ends_at": "2024-07-01T10:00:00Z",
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["all_day"] is False
    assert updated["start_date"] is None
    assert updated["end_date"] is None
    assert updated["starts_at"] is not None
