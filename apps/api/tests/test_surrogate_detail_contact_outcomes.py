from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import Organization, Surrogate, SurrogateContactAttempt


async def _create_surrogate(authed_client, *, name: str) -> uuid.UUID:
    response = await authed_client.post(
        "/surrogates",
        json={"full_name": name, "email": f"contact-{uuid.uuid4().hex}@example.com"},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


def _contact(db, surrogate, test_auth, *, outcome, attempted_at, created_at, org_id=None):
    db.add(
        SurrogateContactAttempt(
            id=uuid.uuid4(),
            surrogate_id=surrogate.id,
            organization_id=org_id or test_auth.org.id,
            attempted_by_user_id=test_auth.user.id,
            contact_methods=["phone"],
            outcome=outcome,
            notes=None,
            attempted_at=attempted_at,
            created_at=created_at,
            surrogate_owner_id_at_attempt=surrogate.owner_id,
        )
    )


@pytest.mark.asyncio
async def test_surrogate_detail_contact_summary_uses_attempt_time(authed_client, db, test_auth):
    surrogate_id = await _create_surrogate(authed_client, name="Contact Summary Candidate")
    surrogate = db.get(Surrogate, surrogate_id)
    now = datetime.now(UTC).replace(microsecond=0)
    _contact(
        db,
        surrogate,
        test_auth,
        outcome="no_answer",
        attempted_at=now - timedelta(minutes=5),
        created_at=now - timedelta(minutes=4),
    )
    _contact(
        db,
        surrogate,
        test_auth,
        outcome="reached",
        attempted_at=now - timedelta(minutes=10),
        created_at=now - timedelta(minutes=1),
    )
    db.commit()

    response = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert response.status_code == 200
    summary = response.json()["latest_contact_outcome"]
    assert summary["outcome"] == "no_answer"
    assert datetime.fromisoformat(summary["at"].replace("Z", "+00:00")) == now - timedelta(
        minutes=5
    )


@pytest.mark.asyncio
async def test_surrogate_detail_contact_summary_is_null_without_attempts(authed_client):
    surrogate_id = await _create_surrogate(authed_client, name="No Contact Summary")
    response = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert response.status_code == 200
    assert response.json()["latest_contact_outcome"] is None


@pytest.mark.asyncio
async def test_surrogate_detail_contact_summary_ignores_cross_org_rows(
    authed_client, db, test_auth
):
    surrogate_id = await _create_surrogate(authed_client, name="Scoped Contact Summary")
    surrogate = db.get(Surrogate, surrogate_id)
    other_org = Organization(
        id=uuid.uuid4(), name="Other Contact Org", slug=f"other-{uuid.uuid4().hex}"
    )
    db.add(other_org)
    db.flush()
    now = datetime.now(UTC).replace(microsecond=0)
    expected_at = now - timedelta(minutes=15)
    _contact(
        db,
        surrogate,
        test_auth,
        outcome="voicemail",
        attempted_at=expected_at,
        created_at=expected_at,
    )
    _contact(
        db,
        surrogate,
        test_auth,
        outcome="wrong_number",
        attempted_at=now - timedelta(minutes=1),
        created_at=now - timedelta(minutes=1),
        org_id=other_org.id,
    )
    db.commit()

    response = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert response.status_code == 200
    summary = response.json()["latest_contact_outcome"]
    assert summary["outcome"] == "voicemail"
    assert datetime.fromisoformat(summary["at"].replace("Z", "+00:00")) == expected_at
