"""
Tests for Match Events endpoints.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.db.models import Case, IntendedParent, Match


def _create_case(db, org_id, user_id, stage):
    case = Case(
        id=uuid.uuid4(),
        organization_id=org_id,
        case_number=f"C{uuid.uuid4().hex[:9]}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Test Case",
        email=f"case-{uuid.uuid4().hex[:8]}@example.com",
    )
    db.add(case)
    db.flush()
    return case


def _create_intended_parent(db, org_id):
    ip = IntendedParent(
        id=uuid.uuid4(),
        organization_id=org_id,
        full_name="Test IP",
        email=f"ip-{uuid.uuid4().hex[:8]}@example.com",
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
        case_id=case.id,
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
