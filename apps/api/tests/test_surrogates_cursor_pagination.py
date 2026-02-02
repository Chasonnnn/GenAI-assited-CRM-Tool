from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service


@pytest.mark.asyncio
async def test_surrogates_list_cursor_pagination(authed_client, db, test_org, test_user):
    s1 = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Cursor One",
            email=f"cursor-one-{uuid4().hex[:8]}@example.com",
        ),
    )
    s2 = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Cursor Two",
            email=f"cursor-two-{uuid4().hex[:8]}@example.com",
        ),
    )
    s3 = surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Cursor Three",
            email=f"cursor-three-{uuid4().hex[:8]}@example.com",
        ),
    )
    s1.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    s2.created_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
    s3.created_at = datetime(2025, 1, 3, tzinfo=timezone.utc)
    db.commit()

    first_page = await authed_client.get("/surrogates?per_page=2")
    assert first_page.status_code == 200
    payload = first_page.json()
    cursor = payload.get("next_cursor")
    assert cursor is not None
    ids_page1 = [item["id"] for item in payload["items"]]
    assert ids_page1 == [str(s3.id), str(s2.id)]

    second_page = await authed_client.get(f"/surrogates?per_page=2&cursor={cursor}")
    assert second_page.status_code == 200
    payload2 = second_page.json()
    ids_page2 = [item["id"] for item in payload2["items"]]
    assert ids_page2 == [str(s1.id)]
    assert payload2.get("next_cursor") is None
    assert payload2.get("total") is None
    assert payload2.get("pages") is None

    second_page_with_total = await authed_client.get(
        f"/surrogates?per_page=2&cursor={cursor}&include_total=true"
    )
    assert second_page_with_total.status_code == 200
    payload3 = second_page_with_total.json()
    assert payload3.get("total") == 3
    assert payload3.get("pages") == 2
