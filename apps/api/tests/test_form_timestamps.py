"""Form timestamps retain their UTC instant in storage and API responses."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from tests.test_form_routing import routing_submission


@pytest.mark.asyncio
async def test_submission_read_preserves_offset_for_browser_local_time(
    authed_client, db, test_org, test_user
):
    form, submission = routing_submission(db, test_org.id, test_user.id)
    submission.submitted_at = datetime(2026, 10, 3, 23, 49, tzinfo=UTC)
    db.commit()
    db.expire_all()

    response = await authed_client.get(f"/forms/{form.id}/submissions")

    assert response.status_code == 200, response.text
    [row] = response.json()
    submitted = datetime.fromisoformat(row["submitted_at"])
    assert submitted.utcoffset() is not None
    assert submitted == datetime(2026, 10, 3, 23, 49, tzinfo=UTC)
    assert submitted.astimezone(ZoneInfo("America/New_York")).hour == 19


@pytest.mark.asyncio
async def test_link_expiry_input_without_offset_keeps_legacy_utc_meaning(
    authed_client, db, test_org, test_user
):
    form, _ = routing_submission(db, test_org.id, test_user.id)
    # Explicit UTC normalization is required before a timestamptz write on this connection.
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    created = await authed_client.post(
        f"/forms/{form.id}/intake-links", json={"expires_at": "2030-10-03T23:49:00"}
    )
    assert created.status_code == 200, created.text
    assert datetime.fromisoformat(created.json()["expires_at"]) == datetime(
        2030, 10, 3, 23, 49, tzinfo=UTC
    )
    updated = await authed_client.patch(
        f"/forms/intake-links/{created.json()['id']}", json={"expires_at": "2030-10-04T23:49:00"}
    )
    assert updated.status_code == 200, updated.text
    assert datetime.fromisoformat(updated.json()["expires_at"]) == datetime(
        2030, 10, 4, 23, 49, tzinfo=UTC
    )
