from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.db.enums import NotificationType, TaskStatus
from app.services import notification_service, task_service


def test_notification_settings_defaults_include_important_change_toggles(db, test_user, test_org):
    settings = notification_service.get_user_settings(db, test_user.id, test_org.id)

    assert settings["status_change_decisions"] is True
    assert settings["approval_timeouts"] is True
    assert settings["security_alerts"] is True


def test_status_change_resolution_uses_status_change_decisions_toggle(monkeypatch, db):
    captured: dict = {}

    def fake_should_notify(_db, _user_id, _org_id, setting_key: str) -> bool:
        captured["setting_key"] = setting_key
        return False

    def fake_create_notification(**kwargs):
        captured["notification"] = kwargs
        return None

    monkeypatch.setattr(notification_service, "should_notify", fake_should_notify)
    monkeypatch.setattr(notification_service, "create_notification", fake_create_notification)

    request = SimpleNamespace(id=uuid4(), requested_by_user_id=uuid4())
    surrogate = SimpleNamespace(id=uuid4(), organization_id=uuid4(), surrogate_number="S10001")

    notification_service.notify_status_change_request_resolved(
        db=db,
        request=request,
        surrogate=surrogate,
        approved=True,
        resolver_name="Approver",
    )

    assert captured["setting_key"] == "status_change_decisions"
    assert "notification" not in captured


def test_attachment_infected_respects_security_alerts_toggle(monkeypatch, db):
    captured: dict = {}

    def fake_should_notify(_db, _user_id, _org_id, setting_key: str) -> bool:
        captured["setting_key"] = setting_key
        return False

    def fake_create_notification(**kwargs):
        captured["notification"] = kwargs
        return None

    monkeypatch.setattr(notification_service, "should_notify", fake_should_notify)
    monkeypatch.setattr(notification_service, "create_notification", fake_create_notification)

    attachment = SimpleNamespace(
        id=uuid4(),
        uploaded_by_user_id=uuid4(),
        organization_id=uuid4(),
        filename="infected.pdf",
        surrogate_id=uuid4(),
    )

    notification_service.notify_attachment_infected(db, attachment)

    assert captured["setting_key"] == "security_alerts"
    assert "notification" not in captured


def test_expire_approval_task_notifies_with_workflow_approval_expired_type(monkeypatch):
    from app.services import notification_facade

    class DummyDB:
        commits = 0

        def commit(self):
            self.commits += 1

    db = DummyDB()
    task = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        owner_id=uuid4(),
        title="Approve critical change",
        status=TaskStatus.PENDING.value,
        workflow_execution_id=None,
        workflow_action_index=None,
        updated_at=None,
    )

    captured: dict = {}

    def fake_should_notify(_db, _user_id, _org_id, setting_key: str) -> bool:
        captured["setting_key"] = setting_key
        return True

    def fake_create_notification(**kwargs):
        captured["notification"] = kwargs
        return None

    monkeypatch.setattr(notification_facade, "should_notify", fake_should_notify)
    monkeypatch.setattr(notification_facade, "create_notification", fake_create_notification)

    task_service.expire_approval_task(db, task)

    assert captured["setting_key"] == "approval_timeouts"
    assert captured["notification"]["type"] == NotificationType.WORKFLOW_APPROVAL_EXPIRED
