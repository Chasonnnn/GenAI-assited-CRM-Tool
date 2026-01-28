from uuid import uuid4

from app.db.enums import NotificationType
from app.services import notification_facade


def test_notification_facade_create_notification_delegates(monkeypatch):
    called = {}

    def fake_create_notification(**kwargs):
        called["kwargs"] = kwargs
        return "sentinel"

    monkeypatch.setattr(
        notification_facade.notification_service,
        "create_notification",
        fake_create_notification,
    )

    db = object()
    org_id = uuid4()
    user_id = uuid4()
    entity_id = uuid4()

    result = notification_facade.create_notification(
        db=db,
        org_id=org_id,
        user_id=user_id,
        type=NotificationType.TASK_ASSIGNED,
        title="Task assigned",
        body="New task",
        entity_type="task",
        entity_id=entity_id,
        dedupe_key="task_assigned:123",
        dedupe_window_hours=3,
    )

    assert result == "sentinel"
    assert called["kwargs"]["db"] is db
    assert called["kwargs"]["org_id"] == org_id
    assert called["kwargs"]["user_id"] == user_id
    assert called["kwargs"]["type"] == NotificationType.TASK_ASSIGNED


def test_notification_facade_notify_task_assigned_delegates(monkeypatch):
    called = {}

    def fake_notify_task_assigned(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs

    monkeypatch.setattr(
        notification_facade.notification_service,
        "notify_task_assigned",
        fake_notify_task_assigned,
    )

    db = object()
    task_id = uuid4()
    org_id = uuid4()
    assignee_id = uuid4()

    notification_facade.notify_task_assigned(
        db=db,
        task_id=task_id,
        task_title="Follow up",
        org_id=org_id,
        assignee_id=assignee_id,
        actor_name="Case Manager",
        surrogate_number="S10023",
    )

    assert called["args"][0] is db
    assert called["args"][1] == task_id
    assert called["args"][3] == org_id
    assert called["args"][4] == assignee_id
    assert called["args"][5] == "Case Manager"
    assert called["kwargs"] == {}
