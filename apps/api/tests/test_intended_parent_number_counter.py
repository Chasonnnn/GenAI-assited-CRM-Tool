"""Intended parent numbers stay unique when the org counter falls behind existing rows."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db.models import IntendedParent
from app.services import ip_service
from scripts import seed_mock_data


def _payload() -> dict:
    return {
        "full_name": "Counter Test Parent",
        "email": f"counter-{uuid.uuid4().hex[:8]}@example.com",
    }


def _counter_value(db, org_id) -> int | None:
    return db.execute(
        text(
            "SELECT current_value FROM org_counters "
            "WHERE organization_id = :org_id AND counter_type = 'intended_parent_number'"
        ),
        {"org_id": org_id},
    ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_create_after_seed_uses_the_next_unused_number(authed_client, db, test_auth):
    seed_mock_data.create_intended_parents(db, test_auth.org.id, test_auth.user.id, count=3)
    assert _counter_value(db, test_auth.org.id) == 10003

    response = await authed_client.post("/intended-parents", json=_payload())

    assert response.status_code == 201, response.text
    assert response.json()["intended_parent_number"] == "I10004"


@pytest.mark.asyncio
async def test_create_repairs_a_counter_behind_existing_numbers(authed_client, db, test_auth):
    for _ in range(3):
        created = await authed_client.post("/intended-parents", json=_payload())
        assert created.status_code == 201, created.text
    db.execute(
        text(
            "UPDATE org_counters SET current_value = 10001 "
            "WHERE organization_id = :org_id AND counter_type = 'intended_parent_number'"
        ),
        {"org_id": test_auth.org.id},
    )
    db.flush()

    response = await authed_client.post("/intended-parents", json=_payload())

    assert response.status_code == 201, response.text
    assert response.json()["intended_parent_number"] == "I10004"
    assert _counter_value(db, test_auth.org.id) == 10004


@pytest.mark.asyncio
async def test_create_returns_sanitized_409_when_number_stays_taken(
    authed_client, db, test_auth, monkeypatch
):
    existing = await authed_client.post("/intended-parents", json=_payload())
    assert existing.status_code == 201, existing.text
    taken_number = existing.json()["intended_parent_number"]
    monkeypatch.setattr(ip_service, "generate_intended_parent_number", lambda *_: taken_number)

    response = await authed_client.post("/intended-parents", json=_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "Couldn't assign an intended parent number. Try again."
    count = db.query(IntendedParent).filter(IntendedParent.organization_id == test_auth.org.id)
    assert count.count() == 1
