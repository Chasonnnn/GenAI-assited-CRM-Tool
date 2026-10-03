"""Daily notification digest email."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.db.enums import JobType, NotificationType
from app.db.models import EmailLog, Job, Membership, Notification
from app.services import notification_digest_service, notification_service
from tests.test_notification_email import _other_org_member, platform_sender  # noqa: F401

NOW = datetime(2026, 10, 3, 12, 30, tzinfo=UTC)  # 08:30 in New York


@pytest.fixture
def ny_org(db, test_org):
    test_org.timezone = "America/New_York"
    db.flush()
    return test_org


def _opt_in(db, user, org, enabled: bool = True) -> None:
    notification_service.update_user_settings(db, user.id, org.id, {"email_daily_digest": enabled})


def _notify(db, org_id, user_id, type, title, *, created_at=None, read=False):
    notification = notification_service.create_notification(
        db=db, org_id=org_id, user_id=user_id, type=type, title=title
    )
    if notification is None:
        notification = Notification(
            organization_id=org_id, user_id=user_id, type=type.value, title=title
        )
        db.add(notification)
    notification.created_at = created_at or NOW - timedelta(hours=1)
    if read:
        notification.read_at = NOW
    db.flush()
    return notification


def _digest_emails(db, org_id):
    return (
        db.query(EmailLog)
        .filter(
            EmailLog.source_type == notification_digest_service.SOURCE_TYPE,
            EmailLog.organization_id == org_id,
        )
        .all()
    )


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 10, 3, 11, 59, tzinfo=UTC), None),  # 07:59 local
        (datetime(2026, 10, 3, 12, 0, tzinfo=UTC), date(2026, 10, 3)),  # 08:00
        (datetime(2026, 10, 3, 15, 59, tzinfo=UTC), date(2026, 10, 3)),  # 11:59
        (datetime(2026, 10, 3, 16, 0, tzinfo=UTC), None),  # 12:00
    ],
)
def test_digest_is_due_in_the_org_morning_window(ny_org, now, expected):
    assert notification_digest_service.due_digest_date(ny_org, now) == expected


def test_schedules_one_job_per_org_and_day_only_with_opted_in_members(db, test_user, ny_org):
    def jobs():
        return (
            db.query(Job)
            .filter(
                Job.organization_id == ny_org.id,
                Job.job_type == JobType.NOTIFICATION_DIGEST.value,
            )
            .all()
        )

    notification_digest_service.schedule_due_digest_jobs(db, NOW)
    assert jobs() == []

    _opt_in(db, test_user, ny_org)
    notification_digest_service.schedule_due_digest_jobs(db, NOW)
    notification_digest_service.schedule_due_digest_jobs(db, NOW + timedelta(hours=1))
    [job] = jobs()
    assert job.payload == {"org_id": str(ny_org.id), "digest_date": "2026-10-03"}

    notification_digest_service.schedule_due_digest_jobs(db, NOW + timedelta(days=1))
    assert len(jobs()) == 2


@pytest.mark.usefixtures("platform_sender")
def test_digest_lists_open_actions_and_recent_unread_updates(db, test_user, ny_org):
    _opt_in(db, test_user, ny_org)
    _notify(db, ny_org.id, test_user.id, NotificationType.ATTACHMENT_INFECTED, "File <quarantined>")
    _notify(
        db, ny_org.id, test_user.id, NotificationType.SURROGATE_STATUS_CHANGED, "Moved to Match"
    )
    _notify(
        db,
        ny_org.id,
        test_user.id,
        NotificationType.SURROGATE_STATUS_CHANGED,
        "Old update",
        created_at=NOW - timedelta(hours=30),
    )
    _notify(
        db,
        ny_org.id,
        test_user.id,
        NotificationType.SURROGATE_STATUS_CHANGED,
        "Read update",
        read=True,
    )

    stats = notification_digest_service.send_org_digests(db, ny_org.id, NOW.date(), NOW)
    again = notification_digest_service.send_org_digests(db, ny_org.id, NOW.date(), NOW)

    assert stats["queued"] == 1
    assert again["queued"] == 1  # Same idempotency key; no second email.
    [email] = _digest_emails(db, ny_org.id)
    assert email.recipient_email == test_user.email
    assert email.subject == "1 need action · 1 new update"
    assert email.source_id == test_user.id
    assert "File &lt;quarantined&gt;" in email.body
    assert "Moved to Match" in email.body
    assert "Old update" not in email.body
    assert "Read update" not in email.body


@pytest.mark.usefixtures("platform_sender")
def test_no_digest_when_nothing_to_report_or_not_opted_in(db, test_user, ny_org):
    _opt_in(db, test_user, ny_org)
    assert notification_digest_service.send_org_digests(db, ny_org.id, NOW.date(), NOW) == {
        "queued": 0,
        "empty": 1,
        "failed": 0,
    }

    _opt_in(db, test_user, ny_org, enabled=False)
    _notify(db, ny_org.id, test_user.id, NotificationType.SURROGATE_STATUS_CHANGED, "Moved")
    notification_digest_service.send_org_digests(db, ny_org.id, NOW.date(), NOW)
    assert _digest_emails(db, ny_org.id) == []


@pytest.mark.usefixtures("platform_sender")
def test_digest_excludes_other_org_members_and_notifications(db, test_user, ny_org):
    other_org, other_user = _other_org_member(db)
    _opt_in(db, other_user, other_org)
    _opt_in(db, test_user, ny_org)
    _notify(db, ny_org.id, test_user.id, NotificationType.SURROGATE_STATUS_CHANGED, "Ours")
    db.add(
        Notification(
            organization_id=other_org.id,
            user_id=test_user.id,
            type=NotificationType.SURROGATE_STATUS_CHANGED.value,
            title="Theirs",
            created_at=NOW - timedelta(hours=1),
        )
    )
    db.flush()

    notification_digest_service.send_org_digests(db, ny_org.id, NOW.date(), NOW)

    [email] = _digest_emails(db, ny_org.id)
    assert email.recipient_email == test_user.email
    assert "Ours" in email.body
    assert "Theirs" not in email.body
    assert _digest_emails(db, other_org.id) == []


def test_delivery_rechecks_membership_preference_and_address(db, test_user, ny_org):
    _opt_in(db, test_user, ny_org)

    def eligible(org_id=ny_org.id, recipient=test_user.email):
        return notification_digest_service.is_digest_delivery_eligible(
            db, org_id, test_user.id, recipient
        )

    assert eligible() is True
    assert eligible(recipient="someone-else@test.com") is False
    other_org, _ = _other_org_member(db)
    assert eligible(org_id=other_org.id) is False

    _opt_in(db, test_user, ny_org, enabled=False)
    assert eligible() is False
    _opt_in(db, test_user, ny_org)

    membership = db.query(Membership).filter(Membership.user_id == test_user.id).one()
    membership.is_active = False
    db.flush()
    assert eligible() is False


@pytest.mark.asyncio
async def test_settings_patch_round_trips_digest_preference(authed_client):
    initial = await authed_client.get("/me/settings/notifications")
    assert initial.json()["email_daily_digest"] is False

    patched = await authed_client.patch(
        "/me/settings/notifications", json={"email_daily_digest": True}
    )
    assert patched.status_code == 200
    assert patched.json()["email_daily_digest"] is True
