from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.db.models import SurrogateActivityLog


@pytest.mark.asyncio
async def test_interview_outcome_write_is_removed_but_history_remains(authed_client, db, test_auth):
    create_response = await authed_client.post(
        "/surrogates",
        json={"full_name": "Historical Outcome", "email": f"history-{uuid4()}@example.com"},
    )
    assert create_response.status_code == 201, create_response.text
    surrogate_id = UUID(create_response.json()["id"])

    historical = SurrogateActivityLog(
        id=uuid4(),
        surrogate_id=surrogate_id,
        organization_id=test_auth.org.id,
        activity_type="interview_outcome_logged",
        actor_user_id=test_auth.user.id,
        details={"outcome": "completed", "notes": "Historical record"},
    )
    db.add(historical)
    db.commit()

    write_response = await authed_client.post(
        f"/surrogates/{surrogate_id}/interview-outcomes",
        json={"outcome": "completed"},
    )
    assert write_response.status_code == 404

    history_response = await authed_client.get(f"/surrogates/{surrogate_id}/activity")
    assert history_response.status_code == 200, history_response.text
    item = next(
        entry for entry in history_response.json()["items"] if entry["id"] == str(historical.id)
    )
    assert item["activity_type"] == "interview_outcome_logged"
    assert item["details"] == {"outcome": "completed", "notes": "Historical record"}
