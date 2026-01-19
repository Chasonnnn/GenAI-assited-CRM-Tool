from datetime import datetime, timezone
import pytest

from app.db.models import Notification


@pytest.mark.asyncio
async def test_notifications_cursor_pagination(authed_client, db, test_org, test_user):
    n1 = Notification(
        organization_id=test_org.id,
        user_id=test_user.id,
        type="general",
        title="First",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    n2 = Notification(
        organization_id=test_org.id,
        user_id=test_user.id,
        type="general",
        title="Second",
        created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )
    n3 = Notification(
        organization_id=test_org.id,
        user_id=test_user.id,
        type="general",
        title="Third",
        created_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
    )
    db.add_all([n1, n2, n3])
    db.commit()

    first_page = await authed_client.get("/me/notifications?limit=2")
    assert first_page.status_code == 200
    payload = first_page.json()
    cursor = payload.get("next_cursor")
    assert cursor is not None
    ids_page1 = [item["id"] for item in payload["items"]]
    assert ids_page1 == [str(n3.id), str(n2.id)]

    second_page = await authed_client.get(f"/me/notifications?limit=2&cursor={cursor}")
    assert second_page.status_code == 200
    payload2 = second_page.json()
    ids_page2 = [item["id"] for item in payload2["items"]]
    assert ids_page2 == [str(n1.id)]
    assert payload2.get("next_cursor") is None
