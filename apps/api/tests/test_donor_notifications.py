"""Donor assignment and stage changes notify users like surrogate changes do."""

import uuid

import pytest

from app.core.policies import POLICIES
from app.db.enums import NotificationType, Role, WorkflowTriggerType
from app.db.models import Membership, Notification, User, UserPermissionOverride
from app.schemas.donor import DonorCreate, DonorUpdate
from app.schemas.workflow import WorkflowCreate
from app.services import donor_service, notification_service, pipeline_service, workflow_service
from app.services.workflow_engine import engine


def _member(db, org_id, *, role=Role.ADMIN, name="Donor Teammate") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"donor-notify-{uuid.uuid4().hex[:8]}@example.com",
        display_name=name,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            organization_id=org_id,
            user_id=user.id,
            role=role.value,
            is_active=True,
        )
    )
    db.flush()
    return user


def _donor(db, org_id, creator_id, *, owner_id=None, donor_type="egg"):
    return donor_service.create_donor(
        db,
        org_id,
        creator_id,
        DonorCreate(
            donor_type=donor_type,
            full_name="Notify Donor",
            email=f"notify-{uuid.uuid4().hex[:8]}@example.com",
            owner_type="user" if owner_id else None,
            owner_id=owner_id,
        ),
        emit_workflow_events=False,
    )


def _stage(db, org_id, stage_key, entity_type="egg_donor"):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, entity_type=entity_type)
    return pipeline_service.get_stage_by_key(db, pipeline.id, stage_key)


def _notifications(db, org_id, user_id, notification_type):
    return (
        db.query(Notification)
        .filter(
            Notification.organization_id == org_id,
            Notification.user_id == user_id,
            Notification.type == notification_type.value,
        )
        .all()
    )


def test_donor_assignment_notifies_new_assignee(db, test_org, test_user):
    assignee = _member(db, test_org.id)
    donor = _donor(db, test_org.id, test_user.id)

    donor_service.update_donor(
        db, donor, test_user.id, DonorUpdate(owner_type="user", owner_id=assignee.id)
    )

    (notification,) = _notifications(
        db, test_org.id, assignee.id, NotificationType.SURROGATE_ASSIGNED
    )
    assert notification.title == f"Egg Donor #{donor.donor_number} assigned to you"
    assert notification.body == f"{test_user.display_name} assigned egg donor Notify Donor to you"
    assert (notification.entity_type, notification.entity_id) == ("donor", donor.id)


@pytest.mark.parametrize("case", ["self_assign", "queue", "preference_off", "no_donor_access"])
def test_donor_assignment_notification_is_suppressed(db, test_org, test_user, case):
    from app.db.models import Queue

    assignee = test_user if case == "self_assign" else _member(db, test_org.id)
    donor = _donor(db, test_org.id, test_user.id)
    if case == "preference_off":
        notification_service.update_user_settings(
            db, assignee.id, test_org.id, {"surrogate_assigned": False}
        )
    if case == "no_donor_access":
        db.add(
            UserPermissionOverride(
                organization_id=test_org.id,
                user_id=assignee.id,
                permission=POLICIES["donors"].default.value,
                override_type="revoke",
            )
        )
        db.flush()
    if case == "queue":
        queue = Queue(organization_id=test_org.id, name=f"Donor queue {uuid.uuid4().hex[:6]}")
        db.add(queue)
        db.flush()
        update = DonorUpdate(owner_type="queue", owner_id=queue.id)
    else:
        update = DonorUpdate(owner_type="user", owner_id=assignee.id)

    donor_service.update_donor(db, donor, test_user.id, update)

    assert (
        db.query(Notification)
        .filter(
            Notification.organization_id == test_org.id,
            Notification.type == NotificationType.SURROGATE_ASSIGNED.value,
            Notification.entity_id == donor.id,
        )
        .count()
        == 0
    )


def test_workflow_donor_assignment_notifies_assignee(db, test_org, test_user):
    assignee = _member(db, test_org.id)
    donor = _donor(db, test_org.id, test_user.id, donor_type="sperm")
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name=f"Assign donor {uuid.uuid4()}",
            subject_type="sperm_donor",
            trigger_type=WorkflowTriggerType.DONOR_CREATED,
            actions=[
                {"action_type": "assign_donor", "owner_type": "user", "owner_id": str(assignee.id)}
            ],
        ),
    )

    engine.execute_workflow(
        db,
        workflow,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="sperm_donor",
        subject_id=donor.id,
        event_data={"donor_id": str(donor.id)},
    )

    (notification,) = _notifications(
        db, test_org.id, assignee.id, NotificationType.SURROGATE_ASSIGNED
    )
    assert notification.title == f"Sperm Donor #{donor.donor_number} assigned to you"
    assert notification.body == "Someone assigned sperm donor Notify Donor to you"


def test_donor_stage_change_notifies_owner_and_creator(db, test_org, test_user):
    creator = _member(db, test_org.id, name="Donor Creator")
    owner = _member(db, test_org.id, name="Donor Owner")
    donor = _donor(db, test_org.id, creator.id, owner_id=owner.id)
    old_label = donor.stage.label
    target = _stage(db, test_org.id, "contacted")

    donor_service.change_status(db, donor, target.id, test_user.id, user_role=Role.ADMIN)

    for recipient in (owner, creator):
        (notification,) = _notifications(
            db, test_org.id, recipient.id, NotificationType.SURROGATE_STATUS_CHANGED
        )
        assert notification.title == f"Egg Donor #{donor.donor_number} stage changed"
        assert notification.body == (
            f"{test_user.display_name} changed stage from {old_label} to {target.label}"
        )
        assert (notification.entity_type, notification.entity_id) == ("donor", donor.id)
    assert (
        _notifications(db, test_org.id, test_user.id, NotificationType.SURROGATE_STATUS_CHANGED)
        == []
    )


@pytest.mark.parametrize("case", ["actor_is_owner", "preference_off", "application_submitted"])
def test_donor_stage_change_notification_is_suppressed(db, test_org, test_user, case):
    owner = test_user if case == "actor_is_owner" else _member(db, test_org.id)
    donor = _donor(db, test_org.id, test_user.id, owner_id=owner.id)
    if case == "preference_off":
        notification_service.update_user_settings(
            db, owner.id, test_org.id, {"surrogate_status_changed": False}
        )
    stage_key = "application_submitted" if case == "application_submitted" else "contacted"
    target = _stage(db, test_org.id, stage_key)

    donor_service.change_status(db, donor, target.id, test_user.id, user_role=Role.ADMIN)

    assert (
        db.query(Notification)
        .filter(
            Notification.organization_id == test_org.id,
            Notification.type == NotificationType.SURROGATE_STATUS_CHANGED.value,
            Notification.entity_id == donor.id,
        )
        .count()
        == 0
    )


def test_donor_assignment_rejects_other_org_user_without_notifying(db, test_org, test_user):
    from app.db.models import Organization

    other_org = Organization(
        id=uuid.uuid4(), name="Other Notify Org", slug=f"other-notify-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    outsider_id = _member(db, other_org.id).id
    donor = _donor(db, test_org.id, test_user.id)

    with pytest.raises(ValueError):
        donor_service.update_donor(
            db, donor, test_user.id, DonorUpdate(owner_type="user", owner_id=outsider_id)
        )
    assert db.query(Notification).filter(Notification.user_id == outsider_id).count() == 0
