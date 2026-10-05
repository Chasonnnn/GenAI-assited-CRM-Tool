"""Realtime delivery must outlive the transaction that created a notification."""

from uuid import uuid4

import pytest

from app.db.enums import NotificationType
from app.services import notification_service


@pytest.mark.asyncio
async def test_notification_push_survives_later_commit_and_session_detachment(
    db, test_org, test_user, monkeypatch
):
    pending, sent = [], []
    user_id, org_id, entity_id = test_user.id, test_org.id, uuid4()

    async def capture_send(recipient, message):
        sent.append((recipient, message))

    monkeypatch.setattr(notification_service, "_schedule_ws_send", pending.append)
    monkeypatch.setattr(notification_service, "send_ws_to_user", capture_send)
    notification = notification_service.create_notification(
        db,
        org_id,
        user_id,
        NotificationType.WORKFLOW_NOTIFICATION,
        title="Review complete",
        body="The review was saved.",
        entity_type="surrogate",
        entity_id=entity_id,
    )
    notification_id, created_at = notification.id, notification.created_at

    # Match effects commit again before the background sender necessarily runs.
    # Expiring and detaching forbids the sender from lazy-loading through that Session.
    db.commit()
    db.expunge_all()
    [send] = pending
    await send

    assert sent == [
        (
            user_id,
            {
                "type": "notification",
                "data": {
                    "id": str(notification_id),
                    "type": "workflow_notification",
                    "tier": "update",
                    "title": "Review complete",
                    "body": "The review was saved.",
                    "entity_type": "surrogate",
                    "entity_id": str(entity_id),
                    "read_at": None,
                    "created_at": created_at.isoformat(),
                },
            },
        ),
        (user_id, {"type": "count_update", "data": {"action_count": 0, "updates_unread": 1}}),
    ]
