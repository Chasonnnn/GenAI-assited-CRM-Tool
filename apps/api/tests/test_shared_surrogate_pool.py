"""V2 post-approval ownership stays shared across supported write boundaries."""

from uuid import uuid4

import pytest

from app.db.enums import OwnerType, Role
from app.db.models import OrganizationPermissionPolicy, RecordCollaborator
from app.services import (
    pipeline_service,
    queue_service,
    surrogate_status_service,
    workflow_record_actions,
)
from tests.test_permission_handoff_publication import member, session
from tests.test_record_scopes_v2 import _record


@pytest.mark.parametrize("owner_role", [Role.INTAKE_SPECIALIST, Role.CASE_MANAGER, Role.ADMIN])
def test_approval_moves_every_owner_to_pool_and_retains_only_intake(
    db, test_org, test_user, owner_role
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    owner = member(db, test_org.id, owner_role)
    actor = session(test_org.id, test_user, Role.DEVELOPER)
    record = _record(db, actor, "surrogate", key="under_review", owner_id=owner.id)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    approved = pipeline_service.get_stage_by_key(db, pipeline.id, "approved")

    surrogate_status_service.change_status(
        db, record, approved.id, test_user.id, Role.DEVELOPER, trigger_workflows=False
    )

    pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
    assert record.owner_type == OwnerType.QUEUE.value
    assert record.owner_id == pool.id
    assert record.assigned_at is None
    collaborators = db.query(RecordCollaborator).filter_by(surrogate_id=record.id).all()
    assert {row.user_id for row in collaborators} == (
        {owner.id} if owner_role == Role.INTAKE_SPECIALIST else set()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["claim", "queue_claim", "assign", "release", "queue_assign"])
async def test_shared_pool_rejects_exclusive_ownership_writes(
    authed_client, db, test_org, test_user, operation
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    actor = session(test_org.id, test_user, Role.DEVELOPER)
    record = _record(db, actor, "surrogate", key="approved")
    pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
    other_queue = queue_service.create_queue(db, test_org.id, "Other Queue")
    record.owner_type, record.owner_id = "queue", pool.id
    db.commit()

    if operation == "assign":
        response = await authed_client.patch(
            f"/surrogates/{record.id}/assign",
            json={"owner_type": "user", "owner_id": str(test_user.id)},
        )
    elif operation == "claim":
        response = await authed_client.post(f"/surrogates/{record.id}/claim")
    else:
        action = {"queue_claim": "claim", "release": "release", "queue_assign": "assign"}[operation]
        response = await authed_client.post(
            f"/queues/surrogates/{record.id}/{action}",
            json={"queue_id": str(other_queue.id)} if action != "claim" else None,
        )

    assert response.status_code == 409, response.text
    db.refresh(record)
    assert record.owner_type == "queue" and record.owner_id == pool.id


@pytest.mark.parametrize("operation", ["assign", "owner_type", "owner_id"])
def test_workflow_cannot_reassign_shared_pool_record(db, test_org, test_user, operation):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    actor = session(test_org.id, test_user, Role.DEVELOPER)
    record = _record(db, actor, "surrogate", key="approved")
    pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
    record.owner_type, record.owner_id = "queue", pool.id
    db.commit()

    with pytest.raises(ValueError, match="shared Surrogate Pool"):
        if operation == "assign":
            workflow_record_actions.assign_surrogate(
                db, {"owner_type": "user", "owner_id": str(test_user.id)}, record, uuid4(), 0, None
            )
        else:
            workflow_record_actions.update_field(
                db,
                {
                    "field": operation,
                    "value": "user" if operation == "owner_type" else str(test_user.id),
                },
                record,
                uuid4(),
                0,
                None,
            )
    db.refresh(record)
    assert record.owner_type == "queue" and record.owner_id == pool.id


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"name": "Renamed Pool"}, {"is_active": False}, None])
async def test_shared_pool_queue_cannot_be_renamed_or_deactivated(
    authed_client, db, test_org, test_user, change
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    record = _record(
        db, session(test_org.id, test_user, Role.DEVELOPER), "surrogate", key="approved"
    )
    pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
    record.owner_type, record.owner_id = "queue", pool.id
    db.commit()

    response = (
        await authed_client.delete(f"/queues/{pool.id}")
        if change is None
        else await authed_client.patch(f"/queues/{pool.id}", json=change)
    )
    assert response.status_code == 409, response.text
    db.refresh(pool)
    assert pool.name == "Surrogate Pool" and pool.is_active


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 2])
async def test_shared_pool_flags_and_queue_listing_follow_effective_phase(
    authed_client, db, test_org, test_user, version
):
    from app.db.models import Organization
    from tests.test_record_scopes_v2 import _stage_history

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=version))
    actor = session(test_org.id, test_user, Role.DEVELOPER)
    before = _record(db, actor, "surrogate", key="under_review", suffix=1)
    approved = _record(db, actor, "surrogate", key="approved", suffix=2)
    paused = _record(db, actor, "surrogate", key="on_hold", paused="approved", suffix=3)
    terminal = _record(db, actor, "surrogate", key="lost", suffix=4)
    later = _record(db, actor, "surrogate", key="ready_to_match", suffix=5)
    _stage_history(db, terminal, "surrogate", approved.stage_id, terminal.stage_id)
    pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
    for record in (before, approved, paused, terminal, later):
        record.owner_type, record.owner_id = "queue", pool.id
    foreign_org = Organization(id=uuid4(), name="Other Agency", slug=f"other-{uuid4()}")
    db.add(foreign_org)
    db.flush()
    foreign = _record(
        db, session(foreign_org.id, test_user, Role.DEVELOPER), "surrogate", key="approved"
    )
    db.commit()

    listing = await authed_client.get("/surrogates")
    assert listing.status_code == 200, listing.text
    flags = {item["id"]: item["is_shared_pool"] for item in listing.json()["items"]}
    assert flags == {
        str(record.id): version == 2 and record is not before
        for record in (before, approved, paused, terminal, later)
    }
    for record in (before, terminal):
        detail = await authed_client.get(f"/surrogates/{record.id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["is_shared_pool"] is (version == 2 and record is terminal)
    assert (await authed_client.get(f"/surrogates/{foreign.id}")).status_code == 404
    pool_listing = await authed_client.get("/surrogates/claim-queue")
    assert pool_listing.status_code == 200, pool_listing.text
    assert {item["id"] for item in pool_listing.json()["items"]} == (
        {str(approved.id), str(paused.id), str(terminal.id), str(later.id)}
        if version == 2
        else {str(approved.id)}
    )


def test_regressing_to_preapproval_allows_assignment_without_removing_collaborator(
    db, test_org, test_user
):
    from app.services import surrogate_service

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    actor = session(test_org.id, test_user, Role.DEVELOPER)
    record = _record(db, actor, "surrogate", key="under_review", owner_id=intake.id)
    review_stage_id = record.stage_id
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    approved = pipeline_service.get_stage_by_key(db, pipeline.id, "approved")
    surrogate_status_service.change_status(
        db, record, approved.id, test_user.id, Role.DEVELOPER, trigger_workflows=False
    )
    surrogate_status_service.change_status(
        db,
        record,
        review_stage_id,
        test_user.id,
        Role.DEVELOPER,
        reason="Review again",
        trigger_workflows=False,
    )
    surrogate_service.assign_surrogate(db, record, OwnerType.USER, test_user.id, test_user.id)
    assert record.owner_type == "user" and record.owner_id == test_user.id
    assert (
        db.query(RecordCollaborator).filter_by(surrogate_id=record.id, user_id=intake.id).count()
        == 1
    )


@pytest.mark.parametrize("version", [1, 2])
def test_restored_import_uses_shared_pool_only_after_v2_activation(
    db, test_org, test_user, version
):
    from app.db.models import Queue, Surrogate
    from app.services import admin_import_service
    from tests.test_admin_imports import _build_surrogates_csv

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=version))
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    approved = pipeline_service.get_stage_by_key(db, pipeline.id, "approved")
    new = pipeline_service.get_stage_by_key(db, pipeline.id, "new_unread")
    db.commit()
    checkpoint = db.begin_nested()
    rows = [
        dict(
            id=str(uuid4()),
            surrogate_number=f"S1000{index}",
            stage_id=str(stage.id),
            status_label=stage.label,
            full_name="Imported Applicant",
            email=f"restored-{index}@example.test",
            owner_type="user",
            owner_id=str(intake.id),
            source="manual",
        )
        for index, stage in enumerate((new, approved), 1)
    ]
    assert (
        admin_import_service.import_surrogates_csv(
            db, test_org.id, _build_surrogates_csv(rows), commit=False
        )
        == 2
    )
    records = (
        db.query(Surrogate)
        .filter_by(organization_id=test_org.id)
        .order_by(Surrogate.surrogate_number)
        .all()
    )
    assert records[0].owner_type == "user" and records[0].owner_id == intake.id
    if version == 2:
        pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
        assert records[1].owner_type == "queue" and records[1].owner_id == pool.id
        assert (
            db.query(RecordCollaborator)
            .filter_by(surrogate_id=records[1].id, user_id=intake.id)
            .count()
            == 1
        )
    else:
        assert records[1].owner_type == "user" and records[1].owner_id == intake.id

    checkpoint.rollback()
    db.expire_all()
    assert db.query(Surrogate).filter_by(organization_id=test_org.id).count() == 0
    assert db.query(RecordCollaborator).filter_by(organization_id=test_org.id).count() == 0
    assert (
        db.query(Queue).filter_by(organization_id=test_org.id, name="Surrogate Pool").count() == 0
    )


def test_create_with_approved_default_retains_current_intake_in_pool(db, test_org):
    from app.schemas.surrogate import SurrogateCreate
    from app.services import surrogate_service

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, test_org.id)
    approved = pipeline_service.get_stage_by_key(db, pipeline.id, "approved")
    for stage in pipeline.stages:
        if stage.order < approved.order:
            stage.is_active = False
    db.flush()

    record = surrogate_service.create_surrogate(
        db,
        test_org.id,
        intake.id,
        SurrogateCreate(full_name="Approved Default", email="approved-default@example.com"),
    )
    pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
    assert record.stage_id == approved.id
    assert (
        record.owner_type == "queue" and record.owner_id == pool.id and record.assigned_at is None
    )
    assert (
        db.query(RecordCollaborator).filter_by(surrogate_id=record.id, user_id=intake.id).count()
        == 1
    )


def test_reviewed_transfer_reactivates_existing_pool_without_reassigning_record(
    db, test_org, test_user
):
    from app.db.models import AuditLog
    from app.services import approval_handoff_service

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    record = _record(
        db, session(test_org.id, test_user, Role.DEVELOPER), "surrogate", key="approved"
    )
    pool = queue_service.get_or_create_surrogate_pool_queue(db, test_org.id)
    record.owner_type, record.owner_id, record.assigned_at = "queue", pool.id, None
    pool.is_active = False
    db.commit()
    plan = approval_handoff_service.build_surrogate_pool_transfer_plan(db, test_org.id)
    assert [row["record_id"] for row in plan] == [str(record.id)]
    assert (
        approval_handoff_service.apply_surrogate_pool_transfers(db, test_org.id, test_user.id, plan)
        == 1
    )
    db.flush()
    assert pool.is_active
    assert record.owner_type == "queue" and record.owner_id == pool.id
    assert any(
        event.details.get("operation") == "reactivate_shared_surrogate_pool"
        for event in db.query(AuditLog)
        .filter_by(organization_id=test_org.id, target_id=pool.id)
        .all()
    )
