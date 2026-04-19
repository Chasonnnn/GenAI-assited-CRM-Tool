from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest

from app.db.models import Organization, Surrogate, SurrogateActivityLog, SurrogateContactAttempt


async def _create_surrogate(authed_client, *, name: str, email: str) -> uuid.UUID:
    response = await authed_client.post(
        "/surrogates",
        json={
            "full_name": name,
            "email": email,
        },
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_surrogate_detail_outcome_summaries_use_latest_relevant_timestamps(
    authed_client,
    db,
    test_auth,
):
    surrogate_id = await _create_surrogate(
        authed_client,
        name="Outcome Summary Candidate",
        email=f"outcome-summary-{uuid.uuid4().hex[:8]}@example.com",
    )
    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate is not None

    now = datetime.now(timezone.utc).replace(microsecond=0)

    db.add_all(
        [
            SurrogateContactAttempt(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                organization_id=test_auth.org.id,
                attempted_by_user_id=test_auth.user.id,
                contact_methods=["phone"],
                outcome="no_answer",
                notes=None,
                attempted_at=now - timedelta(minutes=5),
                created_at=now - timedelta(minutes=4),
                surrogate_owner_id_at_attempt=surrogate.owner_id,
            ),
            SurrogateContactAttempt(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                organization_id=test_auth.org.id,
                attempted_by_user_id=test_auth.user.id,
                contact_methods=["phone"],
                outcome="reached",
                notes=None,
                attempted_at=now - timedelta(minutes=10),
                created_at=now - timedelta(minutes=1),
                surrogate_owner_id_at_attempt=surrogate.owner_id,
            ),
            SurrogateActivityLog(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                organization_id=test_auth.org.id,
                activity_type="interview_outcome_logged",
                actor_user_id=test_auth.user.id,
                details={"outcome": "no_show", "occurred_at": (now - timedelta(minutes=3)).isoformat()},
                created_at=now - timedelta(minutes=3),
            ),
            SurrogateActivityLog(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                organization_id=test_auth.org.id,
                activity_type="interview_outcome_logged",
                actor_user_id=test_auth.user.id,
                details={"outcome": "completed", "occurred_at": (now - timedelta(minutes=8)).isoformat()},
                created_at=now - timedelta(minutes=1),
            ),
        ]
    )
    db.commit()

    response = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["latest_contact_outcome"]["outcome"] == "no_answer"
    assert datetime.fromisoformat(
        payload["latest_contact_outcome"]["at"].replace("Z", "+00:00")
    ) == now - timedelta(minutes=5)
    assert payload["latest_interview_outcome"]["outcome"] == "no_show"
    assert datetime.fromisoformat(
        payload["latest_interview_outcome"]["at"].replace("Z", "+00:00")
    ) == now - timedelta(minutes=3)


@pytest.mark.asyncio
async def test_surrogate_detail_outcome_summaries_are_null_without_records(authed_client):
    surrogate_id = await _create_surrogate(
        authed_client,
        name="No Outcome Summary",
        email=f"no-outcome-summary-{uuid.uuid4().hex[:8]}@example.com",
    )

    response = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["latest_contact_outcome"] is None
    assert payload["latest_interview_outcome"] is None


@pytest.mark.asyncio
async def test_surrogate_detail_outcome_summaries_ignore_cross_org_rows(
    authed_client,
    db,
    test_auth,
):
    surrogate_id = await _create_surrogate(
        authed_client,
        name="Scoped Outcome Summary",
        email=f"scoped-outcome-summary-{uuid.uuid4().hex[:8]}@example.com",
    )
    surrogate = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
    assert surrogate is not None

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Outcome Org",
        slug=f"other-outcome-org-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    same_org_contact_at = now - timedelta(minutes=15)
    same_org_interview_at = now - timedelta(minutes=12)

    db.add_all(
        [
            SurrogateContactAttempt(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                organization_id=test_auth.org.id,
                attempted_by_user_id=test_auth.user.id,
                contact_methods=["phone"],
                outcome="voicemail",
                notes=None,
                attempted_at=same_org_contact_at,
                created_at=same_org_contact_at,
                surrogate_owner_id_at_attempt=surrogate.owner_id,
            ),
            SurrogateContactAttempt(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                organization_id=other_org.id,
                attempted_by_user_id=test_auth.user.id,
                contact_methods=["phone"],
                outcome="wrong_number",
                notes=None,
                attempted_at=now - timedelta(minutes=1),
                created_at=now - timedelta(minutes=1),
                surrogate_owner_id_at_attempt=surrogate.owner_id,
            ),
            SurrogateActivityLog(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                organization_id=test_auth.org.id,
                activity_type="interview_outcome_logged",
                actor_user_id=test_auth.user.id,
                details={"outcome": "rescheduled", "occurred_at": same_org_interview_at.isoformat()},
                created_at=same_org_interview_at,
            ),
            SurrogateActivityLog(
                id=uuid.uuid4(),
                surrogate_id=surrogate_id,
                organization_id=other_org.id,
                activity_type="interview_outcome_logged",
                actor_user_id=test_auth.user.id,
                details={"outcome": "cancelled", "occurred_at": (now - timedelta(minutes=2)).isoformat()},
                created_at=now - timedelta(minutes=2),
            ),
        ]
    )
    db.commit()

    response = await authed_client.get(f"/surrogates/{surrogate_id}")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["latest_contact_outcome"]["outcome"] == "voicemail"
    assert datetime.fromisoformat(
        payload["latest_contact_outcome"]["at"].replace("Z", "+00:00")
    ) == same_org_contact_at
    assert payload["latest_interview_outcome"]["outcome"] == "rescheduled"
    assert datetime.fromisoformat(
        payload["latest_interview_outcome"]["at"].replace("Z", "+00:00")
    ) == same_org_interview_at
