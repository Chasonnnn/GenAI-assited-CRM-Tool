"""Opt-in email channel for in-app notifications."""

from __future__ import annotations

import logging
import uuid

import pytest

from app.db.enums import EmailDeliveryStatus, EmailStatus, NotificationType, Role
from app.db.models import (
    EmailDelivery,
    EmailLog,
    Membership,
    Organization,
    User,
    UserNotificationSettings,
)
from app.services import notification_email_service, notification_service

BODY = "Applicant Jane Roe submitted a new application"


@pytest.fixture
def platform_sender(monkeypatch):
    from app.services import platform_email_service

    monkeypatch.setattr(platform_email_service.settings, "PLATFORM_RESEND_API_KEY", "re_test")
    monkeypatch.setattr(
        platform_email_service.settings,
        "PLATFORM_EMAIL_FROM",
        "Surrogacy Force <notify@surrogacyforce.com>",
    )
    monkeypatch.setattr(notification_email_service.org_service.settings, "PLATFORM_BASE_DOMAIN", "")
    monkeypatch.setattr(
        notification_email_service.org_service.settings, "FRONTEND_URL", "https://app.test"
    )


def _opt_in(db, user, org, enabled: bool = True) -> None:
    notification_service.update_user_settings(
        db, user.id, org.id, {"email_workflow_notifications": enabled}
    )


def _notify(db, org_id, user_id, *, type=NotificationType.WORKFLOW_NOTIFICATION, **kwargs):
    return notification_service.create_notification(
        db=db,
        org_id=org_id,
        user_id=user_id,
        type=type,
        title=kwargs.pop("title", "New application"),
        body=kwargs.pop("body", BODY),
        **kwargs,
    )


def _notification_emails(db, org_id=None):
    query = db.query(EmailLog).filter(EmailLog.source_type == "notification_email")
    if org_id is not None:
        query = query.filter(EmailLog.organization_id == org_id)
    return query.all()


def _other_org_member(db):
    org = Organization(id=uuid.uuid4(), name="Other Org", slug=f"other-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    user = User(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(Membership(id=uuid.uuid4(), user_id=user.id, organization_id=org.id, role=Role.ADMIN))
    db.flush()
    return org, user


def test_email_preference_defaults_off_and_in_app_defaults_on(db, test_user, test_org):
    settings = notification_service.get_user_settings(db, test_user.id, test_org.id)

    assert settings["email_workflow_notifications"] is False
    assert settings["surrogate_assigned"] is True

    row = UserNotificationSettings(user_id=test_user.id, organization_id=test_org.id)
    db.add(row)
    db.flush()
    db.refresh(row)
    assert row.email_workflow_notifications is False
    assert row.task_assigned is True


@pytest.mark.asyncio
async def test_settings_patch_round_trips_email_preference(authed_client):
    initial = await authed_client.get("/me/settings/notifications")
    assert initial.status_code == 200
    assert initial.json()["email_workflow_notifications"] is False

    patched = await authed_client.patch(
        "/me/settings/notifications", json={"email_workflow_notifications": True}
    )
    assert patched.status_code == 200
    assert patched.json()["email_workflow_notifications"] is True
    assert patched.json()["task_assigned"] is True

    reread = await authed_client.get("/me/settings/notifications")
    assert reread.json()["email_workflow_notifications"] is True


@pytest.mark.asyncio
async def test_settings_patch_requires_csrf(authed_client):
    from app.core.csrf import CSRF_HEADER

    authed_client.headers.pop(CSRF_HEADER, None)
    response = await authed_client.patch(
        "/me/settings/notifications", json={"email_workflow_notifications": True}
    )
    assert response.status_code == 403


def test_no_email_when_preference_off(db, test_user, test_org, platform_sender):
    notification = _notify(db, test_org.id, test_user.id)

    assert notification is not None
    assert _notification_emails(db) == []


def test_email_queued_when_preference_on(db, test_user, test_org, platform_sender):
    _opt_in(db, test_user, test_org)
    surrogate_id = uuid.uuid4()

    notification = _notify(
        db, test_org.id, test_user.id, entity_type="surrogate", entity_id=surrogate_id
    )

    [email_log] = _notification_emails(db)
    assert email_log.organization_id == test_org.id
    assert email_log.recipient_email == test_user.email.lower()
    assert email_log.source_id == notification.id
    assert email_log.idempotency_key == f"notification-email:{notification.id}"
    assert email_log.surrogate_id is None
    assert email_log.subject == "New application"
    assert email_log.status == EmailStatus.PENDING.value
    record_url = f"https://app.test/surrogates/{surrogate_id}"
    assert record_url in email_log.body
    assert BODY in email_log.body
    assert email_log.text_body == f"New application\n\n{BODY}\n\nView record: {record_url}\n"
    delivery = db.query(EmailDelivery).filter(EmailDelivery.email_log_id == email_log.id).one()
    assert delivery.status == EmailDeliveryStatus.PENDING.value
    assert delivery.organization_id == test_org.id


def test_email_omits_link_without_record(db, test_user, test_org, platform_sender):
    _opt_in(db, test_user, test_org)

    _notify(db, test_org.id, test_user.id)

    [email_log] = _notification_emails(db)
    assert "View record" not in email_log.body
    assert email_log.text_body == f"New application\n\n{BODY}\n"


def test_email_escapes_notification_content(db, test_user, test_org, platform_sender):
    _opt_in(db, test_user, test_org)

    _notify(db, test_org.id, test_user.id, title="<b>Lead</b>", body="<script>x</script>")

    [email_log] = _notification_emails(db)
    assert "<script>" not in email_log.body
    assert "&lt;script&gt;" in email_log.body
    assert "<b>Lead</b>" not in email_log.body


def test_no_email_for_types_without_email_toggle(db, test_user, test_org, platform_sender):
    _opt_in(db, test_user, test_org)

    _notify(db, test_org.id, test_user.id, type=NotificationType.TASK_ASSIGNED)

    assert _notification_emails(db) == []


def test_no_email_for_inactive_member(db, test_user, test_org, platform_sender):
    _opt_in(db, test_user, test_org)
    membership = db.query(Membership).filter(Membership.user_id == test_user.id).one()
    membership.is_active = False
    db.flush()

    notification = _notify(db, test_org.id, test_user.id)

    assert notification is not None
    assert _notification_emails(db) == []


def test_no_email_for_notification_in_another_org(db, test_user, test_org, platform_sender):
    _opt_in(db, test_user, test_org)
    other_org, other_user = _other_org_member(db)
    _opt_in(db, other_user, other_org)

    # test_user opted in within test_org but is not a member of other_org.
    _notify(db, other_org.id, test_user.id)
    # other_user opted in within other_org but is not a member of test_org.
    _notify(db, test_org.id, other_user.id)

    assert _notification_emails(db) == []

    _notify(db, other_org.id, other_user.id)
    [email_log] = _notification_emails(db)
    assert email_log.organization_id == other_org.id
    assert email_log.recipient_email == other_user.email.lower()


def test_queue_is_idempotent_per_notification(db, test_user, test_org, platform_sender):
    _opt_in(db, test_user, test_org)
    notification = _notify(db, test_org.id, test_user.id)

    assert notification_email_service.queue_notification_email(db, notification) is True
    assert notification_email_service.queue_notification_email(db, notification) is True
    db.flush()

    assert len(_notification_emails(db)) == 1
    assert (
        db.query(EmailDelivery)
        .filter(EmailDelivery.idempotency_key == f"notification-email:{notification.id}")
        .count()
        == 1
    )


def test_unconfigured_sender_keeps_notification_and_logs_no_content(
    db, test_user, test_org, monkeypatch, caplog
):
    from app.services import platform_email_service

    monkeypatch.setattr(platform_email_service.settings, "PLATFORM_RESEND_API_KEY", "re_test")
    monkeypatch.setattr(platform_email_service.settings, "PLATFORM_EMAIL_FROM", "")
    _opt_in(db, test_user, test_org)

    with caplog.at_level(logging.DEBUG):
        notification = _notify(db, test_org.id, test_user.id)

    assert notification is not None
    assert _notification_emails(db) == []
    assert "Notification email not queued" in caplog.text
    assert test_user.email not in caplog.text
    assert BODY not in caplog.text


def test_enqueue_failure_rolls_back_only_the_email(
    db, test_user, test_org, platform_sender, monkeypatch, caplog
):
    _opt_in(db, test_user, test_org)

    def boom(*_args, **_kwargs):
        raise RuntimeError(f"bad payload {BODY}")

    monkeypatch.setattr(
        notification_email_service.platform_email_service, "queue_email_logged", boom
    )

    with caplog.at_level(logging.ERROR):
        notification = _notify(db, test_org.id, test_user.id)

    assert notification is not None
    assert _notification_emails(db) == []
    assert "error_class=RuntimeError" in caplog.text
    assert BODY not in caplog.text


def test_delivery_rechecks_membership_and_preference(db, test_user, test_org, platform_sender):
    _opt_in(db, test_user, test_org)
    notification = _notify(db, test_org.id, test_user.id)
    [email_log] = _notification_emails(db)

    def eligible(org_id=test_org.id, recipient=email_log.recipient_email):
        return notification_email_service.is_notification_email_delivery_eligible(
            db, org_id, notification.id, recipient
        )

    assert eligible() is True
    assert eligible(recipient="someone-else@test.com") is False
    other_org, _ = _other_org_member(db)
    assert eligible(org_id=other_org.id) is False

    _opt_in(db, test_user, test_org, enabled=False)
    assert eligible() is False
    _opt_in(db, test_user, test_org)

    membership = db.query(Membership).filter(Membership.user_id == test_user.id).one()
    membership.is_active = False
    db.flush()
    assert eligible() is False


@pytest.mark.asyncio
async def test_dispatch_cancels_delivery_for_removed_member(
    db, test_user, test_org, platform_sender, monkeypatch
):
    from datetime import timedelta

    from app.services import email_delivery_dispatch, email_delivery_service

    _opt_in(db, test_user, test_org)
    _notify(db, test_org.id, test_user.id)
    [email_log] = _notification_emails(db)
    membership = db.query(Membership).filter(Membership.user_id == test_user.id).one()
    membership.is_active = False
    db.commit()
    provider_called = False

    async def fake_send_email(**_kwargs):
        nonlocal provider_called
        provider_called = True

    monkeypatch.setattr(email_delivery_dispatch.resend_transport, "send_email", fake_send_email)

    claims = email_delivery_service.claim_due_deliveries(
        db, worker_id="notification-email-test", lease_for=timedelta(minutes=2), limit=50
    )
    [claim] = [c for c in claims if c.email_log_id == email_log.id]
    delivery = await email_delivery_dispatch.dispatch_claim(db, claim=claim)

    assert provider_called is False
    assert delivery.status == EmailDeliveryStatus.CANCELLED.value
    assert delivery.last_error_type == "notification_email_ineligible"


def test_workflow_send_notification_emails_opted_in_owner(db, test_user, test_org, platform_sender):
    from types import SimpleNamespace

    from app.db.enums import OwnerType
    from app.services import workflow_communication_actions

    _opt_in(db, test_user, test_org)
    surrogate = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        created_by_user_id=None,
    )

    result = workflow_communication_actions.send_notification(
        db=db,
        action={"title": "New lead", "body": BODY, "recipients": "owner"},
        entity=surrogate,
    )

    assert result["recipients_count"] == 1
    [email_log] = _notification_emails(db)
    assert email_log.subject == "New lead"
    assert f"/surrogates/{surrogate.id}" in email_log.body


@pytest.mark.parametrize(
    ("type_", "entity_type", "expected"),
    [
        (
            NotificationType.WORKFLOW_APPROVAL_REQUESTED,
            "task",
            "/tasks?filter=my_tasks&focus=approvals&approval={id}",
        ),
        (NotificationType.TASK_ASSIGNED, "donor_task", "/tasks?filter=my_tasks&task={id}"),
        (NotificationType.APPOINTMENT_REQUESTED, "appointment", "/appointments?appointment={id}"),
        (NotificationType.STATUS_CHANGE_REQUESTED, "match", "/intended-parents/matches/{id}"),
    ],
)
def test_record_path_opens_the_exact_record(type_, entity_type, expected):
    from app.db.models import Notification

    entity_id = uuid.uuid4()
    notification = Notification(type=type_.value, entity_type=entity_type, entity_id=entity_id)
    assert notification_email_service.record_path(notification) == expected.format(id=entity_id)
