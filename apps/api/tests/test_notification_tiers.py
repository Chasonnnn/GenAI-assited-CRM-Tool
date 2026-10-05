"""Action-needed vs update tiers: open action items are computed from live domain state."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.db.enums import NotificationTier, NotificationType, OwnerType, TaskStatus, TaskType
from app.db.models import (
    Appointment,
    Notification,
    Organization,
    StatusChangeRequest,
    Surrogate,
    SurrogateContactAttempt,
    Task,
    User,
)
from app.services import notification_service


async def _create_surrogate(authed_client, name: str = "Tier Candidate") -> uuid.UUID:
    response = await authed_client.post(
        "/surrogates",
        json={"full_name": name, "email": f"tier-{uuid.uuid4().hex}@example.com"},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


def _notify(db, org_id, user_id, type_: NotificationType, **kwargs) -> Notification:
    notification = Notification(
        organization_id=org_id,
        user_id=user_id,
        type=type_.value,
        title=kwargs.pop("title", type_.value),
        **kwargs,
    )
    db.add(notification)
    db.flush()
    return notification


def _task(db, test_org, test_user, surrogate_id, **kwargs) -> Task:
    task = Task(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_id=surrogate_id,
        created_by_user_id=test_user.id,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        title=kwargs.pop("title", "Follow up"),
        task_type=kwargs.pop("task_type", TaskType.OTHER.value),
        **kwargs,
    )
    db.add(task)
    db.flush()
    return task


def _open_action_ids(db, test_user, test_org) -> set[uuid.UUID]:
    items, _ = notification_service.get_notifications(
        db, test_user.id, test_org.id, tier=NotificationTier.ACTION, limit=100
    )
    return {item.id for item in items}


def _action_count(db, test_user, test_org) -> int:
    return notification_service.get_notification_counts(db, test_user.id, test_org.id).action


@pytest.mark.asyncio
async def test_approval_item_clears_when_task_is_decided(authed_client, db, test_org, test_user):
    surrogate_id = await _create_surrogate(authed_client)
    task = _task(
        db,
        test_org,
        test_user,
        surrogate_id,
        task_type=TaskType.WORKFLOW_APPROVAL.value,
        status=TaskStatus.PENDING.value,
    )
    item = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.WORKFLOW_APPROVAL_REQUESTED,
        entity_type="task",
        entity_id=task.id,
    )

    assert _open_action_ids(db, test_user, test_org) == {item.id}
    assert _action_count(db, test_user, test_org) == 1

    task.status = TaskStatus.COMPLETED.value
    task.is_completed = True
    db.flush()

    assert _open_action_ids(db, test_user, test_org) == set()
    assert _action_count(db, test_user, test_org) == 0


@pytest.mark.asyncio
async def test_task_items_clear_when_reassigned_or_rescheduled(
    authed_client, db, test_org, test_user
):
    surrogate_id = await _create_surrogate(authed_client)
    overdue_task = _task(db, test_org, test_user, surrogate_id, due_date=date(2020, 1, 1))
    assigned_task = _task(db, test_org, test_user, surrogate_id)
    overdue = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.TASK_OVERDUE,
        entity_type="task",
        entity_id=overdue_task.id,
    )
    assigned = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.TASK_ASSIGNED,
        entity_type="task",
        entity_id=assigned_task.id,
    )
    assert _open_action_ids(db, test_user, test_org) == {overdue.id, assigned.id}

    overdue_task.due_date = datetime.now(UTC).date() + timedelta(days=3)
    assigned_task.owner_id = uuid.uuid4()
    db.flush()

    assert _open_action_ids(db, test_user, test_org) == set()


@pytest.mark.asyncio
async def test_status_change_items_follow_domain_state(authed_client, db, test_org, test_user):
    surrogate_id = await _create_surrogate(authed_client)
    now = datetime.now(UTC)
    request = StatusChangeRequest(
        organization_id=test_org.id,
        entity_type="surrogate",
        entity_id=surrogate_id,
        effective_at=now,
        reason="Correction",
        requested_by_user_id=test_user.id,
        requested_at=now - timedelta(minutes=1),
        status="pending",
    )
    db.add(request)
    db.flush()
    approval = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.STATUS_CHANGE_REQUESTED,
        entity_type="surrogate",
        entity_id=surrogate_id,
    )
    assert _open_action_ids(db, test_user, test_org) == {approval.id}

    request.status = "approved"
    db.flush()

    assert _open_action_ids(db, test_user, test_org) == set()


@pytest.mark.asyncio
async def test_contact_reminder_shows_newest_only_and_clears_on_attempt(
    authed_client, db, test_org, test_user
):
    surrogate_id = await _create_surrogate(authed_client)
    surrogate = db.get(Surrogate, surrogate_id)
    surrogate.owner_type = OwnerType.USER.value
    surrogate.owner_id = test_user.id
    now = datetime.now(UTC)
    _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.CONTACT_REMINDER,
        entity_type="surrogate",
        entity_id=surrogate_id,
        created_at=now - timedelta(days=1),
    )
    newest = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.CONTACT_REMINDER,
        entity_type="surrogate",
        entity_id=surrogate_id,
        created_at=now - timedelta(minutes=5),
    )
    assert _open_action_ids(db, test_user, test_org) == {newest.id}

    db.add(
        SurrogateContactAttempt(
            surrogate_id=surrogate_id,
            organization_id=test_org.id,
            attempted_by_user_id=test_user.id,
            contact_methods=["phone"],
            outcome="no_answer",
            attempted_at=now,
            created_at=now,
            surrogate_owner_id_at_attempt=test_user.id,
        )
    )
    db.flush()

    assert _open_action_ids(db, test_user, test_org) == set()


def test_read_cleared_items_and_appointment_requests(db, test_org, test_user):
    now = datetime.now(UTC)
    appointment = Appointment(
        organization_id=test_org.id,
        user_id=test_user.id,
        client_name="Lena Park",
        client_email=f"{uuid.uuid4()}@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=now + timedelta(days=2),
        scheduled_end=now + timedelta(days=2, minutes=30),
        duration_minutes=30,
        meeting_mode="phone",
        status="pending",
    )
    db.add(appointment)
    db.flush()
    requested = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.APPOINTMENT_REQUESTED,
        entity_type="appointment",
        entity_id=appointment.id,
    )
    assigned = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.SURROGATE_ASSIGNED,
        entity_type="surrogate",
        entity_id=uuid.uuid4(),
    )
    _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.SURROGATE_ASSIGNED,
        entity_type="surrogate",
        entity_id=uuid.uuid4(),
        created_at=now - notification_service.READ_CLEARED_ACTION_WINDOW - timedelta(days=1),
    )
    assert _open_action_ids(db, test_user, test_org) == {requested.id, assigned.id}

    appointment.status = "confirmed"
    assigned.read_at = now
    db.flush()

    assert _open_action_ids(db, test_user, test_org) == set()


@pytest.mark.asyncio
async def test_tier_endpoints_hide_retired_claim_notices_and_preserve_other_notifications(
    authed_client, db, test_org, test_user
):
    surrogate_id = await _create_surrogate(authed_client)
    surrogate = db.get(Surrogate, surrogate_id)
    surrogate.owner_type = OwnerType.QUEUE.value
    surrogate.owner_id = uuid.uuid4()
    claim = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.SURROGATE_CLAIM_AVAILABLE,
        entity_type="surrogate",
        entity_id=surrogate_id,
    )
    read_claim = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.SURROGATE_CLAIM_AVAILABLE,
        entity_type="surrogate",
        entity_id=surrogate_id,
        read_at=datetime.now(UTC),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    task = _task(
        db,
        test_org,
        test_user,
        surrogate_id,
        task_type=TaskType.WORKFLOW_APPROVAL.value,
        status=TaskStatus.PENDING.value,
    )
    action = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.WORKFLOW_APPROVAL_REQUESTED,
        entity_type="task",
        entity_id=task.id,
    )
    update = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.SURROGATE_STATUS_CHANGED,
        entity_type="surrogate",
        entity_id=surrogate_id,
    )
    db.commit()

    counts = await authed_client.get("/me/notifications/count")
    assert counts.status_code == 200
    assert counts.json() == {"action_count": 1, "updates_unread": 1}

    for query in ("", "?unread_only=true"):
        response = await authed_client.get(f"/me/notifications{query}")
        assert response.status_code == 200
        assert {item["id"] for item in response.json()["items"]} == {
            str(action.id),
            str(update.id),
        }
        assert response.json()["unread_count"] == 2
    retired_only = await authed_client.get(
        "/me/notifications?notification_types=surrogate_claim_available"
    )
    assert retired_only.status_code == 200
    assert retired_only.json()["items"] == []

    action_list = (await authed_client.get("/me/notifications?tier=action")).json()
    assert [(item["id"], item["tier"]) for item in action_list["items"]] == [
        (str(action.id), "action")
    ]
    update_list = (await authed_client.get("/me/notifications?tier=update")).json()
    assert [(item["id"], item["tier"]) for item in update_list["items"]] == [
        (str(update.id), "update")
    ]

    marked = await authed_client.post("/me/notifications/read-all?tier=update")
    assert marked.status_code == 200
    assert marked.json() == {"marked_read": 1}
    db.expire_all()
    assert db.get(Notification, update.id).read_at is not None
    assert db.get(Notification, action.id).read_at is None

    counts = await authed_client.get("/me/notifications/count")
    assert counts.json() == {"action_count": 1, "updates_unread": 0}

    assert (await authed_client.patch(f"/me/notifications/{claim.id}/read")).status_code == 404
    marked = await authed_client.post("/me/notifications/read-all")
    assert marked.json() == {"marked_read": 1}
    db.expire_all()
    assert db.get(Notification, claim.id).read_at is None
    assert db.get(Notification, read_claim.id).read_at is not None


def test_counts_and_action_list_exclude_other_organizations(db, test_org, test_user):
    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Tier Org",
        slug=f"other-tier-org-{uuid.uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    other_user = User(
        id=uuid.uuid4(),
        email=f"other-tier-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Other Tier User",
        token_version=1,
        is_active=True,
    )
    db.add(other_user)
    db.flush()
    _notify(
        db,
        other_org.id,
        test_user.id,
        NotificationType.SURROGATE_ASSIGNED,
        entity_type="surrogate",
        entity_id=uuid.uuid4(),
    )
    _notify(db, other_org.id, test_user.id, NotificationType.SURROGATE_STATUS_CHANGED)
    _notify(
        db,
        test_org.id,
        other_user.id,
        NotificationType.SURROGATE_ASSIGNED,
        entity_type="surrogate",
        entity_id=uuid.uuid4(),
    )

    counts = notification_service.get_notification_counts(db, test_user.id, test_org.id)
    assert counts == notification_service.NotificationCounts(action=0, updates_unread=0)
    assert _open_action_ids(db, test_user, test_org) == set()


@pytest.mark.asyncio
async def test_action_list_exposes_the_pending_status_change_request(
    authed_client, db, test_org, test_user
):
    surrogate_id = await _create_surrogate(authed_client)
    now = datetime.now(UTC)
    other_org = Organization(
        id=uuid.uuid4(), name="Request Org", slug=f"request-org-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()

    def _request(org_id, requested_at):
        request = StatusChangeRequest(
            organization_id=org_id,
            entity_type="surrogate",
            entity_id=surrogate_id,
            effective_at=now,
            reason="Correction",
            requested_by_user_id=test_user.id,
            requested_at=requested_at,
            status="pending",
        )
        db.add(request)
        db.flush()
        return request

    ours = _request(test_org.id, now - timedelta(minutes=5))
    # Same entity id in another org, requested later: must never be offered.
    _request(other_org.id, now - timedelta(minutes=1))
    notification = _notify(
        db,
        test_org.id,
        test_user.id,
        NotificationType.STATUS_CHANGE_REQUESTED,
        entity_type="surrogate",
        entity_id=surrogate_id,
        created_at=now,
    )

    items = (await authed_client.get("/me/notifications?tier=action")).json()["items"]
    [item] = [i for i in items if i["id"] == str(notification.id)]
    assert item["request_id"] == str(ours.id)

    ours.status = "approved"
    db.flush()
    items = (await authed_client.get("/me/notifications?tier=action")).json()["items"]
    assert str(notification.id) not in {i["id"] for i in items}
