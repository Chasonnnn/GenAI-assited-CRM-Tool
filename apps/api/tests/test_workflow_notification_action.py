from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.db.enums import NotificationType, OwnerType


def test_workflow_send_notification_uses_workflow_notification_type(monkeypatch):
    from app.services import notification_facade
    from app.services.workflow_engine_adapters import DefaultWorkflowDomainAdapter

    adapter = DefaultWorkflowDomainAdapter()
    captured: dict = {}

    def fake_create_notification(**kwargs):
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr(notification_facade, "create_notification", fake_create_notification)

    owner_id = uuid4()
    surrogate = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        owner_type=OwnerType.USER.value,
        owner_id=owner_id,
        created_by_user_id=None,
    )

    result = adapter._action_send_notification(
        db=SimpleNamespace(),
        action={
            "title": "Workflow sent",
            "body": "Please review this update.",
            "recipients": "owner",
        },
        entity=surrogate,
    )

    assert result["success"] is True
    assert captured["kwargs"]["user_id"] == owner_id
    assert captured["kwargs"]["type"] == NotificationType.WORKFLOW_NOTIFICATION
