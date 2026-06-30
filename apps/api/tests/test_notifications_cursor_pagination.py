from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import event

from app.db.enums import Role
from app.db.models import Membership, Notification, Organization, User
from app.services.notification_service import get_unread_count


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


def test_get_unread_count_uses_direct_count_and_preserves_scope(db, test_org, test_user):
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Notification Org",
        slug=f"other-notification-org-{uuid.uuid4().hex[:8]}",
    )
    other_user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other User",
        token_version=1,
        is_active=True,
    )
    db.add_all([other_org, other_user])
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=other_user.id,
            organization_id=other_org.id,
            role=Role.DEVELOPER,
        )
    )
    db.add_all(
        [
            Notification(
                organization_id=test_org.id,
                user_id=test_user.id,
                type="general",
                title="Unread one",
            ),
            Notification(
                organization_id=test_org.id,
                user_id=test_user.id,
                type="general",
                title="Unread two",
            ),
            Notification(
                organization_id=test_org.id,
                user_id=test_user.id,
                type="general",
                title="Read",
                read_at=datetime.now(timezone.utc),
            ),
            Notification(
                organization_id=other_org.id,
                user_id=other_user.id,
                type="general",
                title="Other org unread",
            ),
        ]
    )
    db.flush()

    statements: list[str] = []

    def capture_count_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if "notifications" in normalized and "count" in normalized:
            statements.append(normalized)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", capture_count_sql)
    try:
        assert get_unread_count(db, test_user.id, test_org.id) == 2
    finally:
        event.remove(bind, "before_cursor_execute", capture_count_sql)

    assert statements
    assert all("from (select" not in statement for statement in statements)
