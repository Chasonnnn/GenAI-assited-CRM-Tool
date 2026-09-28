"""Donor workflow stage regressions that need approval must not report success."""

from uuid import uuid4

from app.db.enums import Role, WorkflowEventSource
from app.db.models import (
    AutomationWorkflow,
    Membership,
    StatusChangeRequest,
    User,
    WorkflowExecution,
)
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.db.models.record_access import RoleRecordScope
from app.schemas.donor import DonorCreate
from app.services import donor_service, pipeline_service
from app.services.workflow_engine import engine


def _stage(db, org_id, stage_key: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, entity_type="egg_donor")
    return pipeline_service.get_stage_by_key(db, pipeline.id, stage_key)


def _case_manager(db, org_id):
    user = User(
        id=uuid4(),
        email=f"donor-regression-{uuid4().hex[:8]}@example.com",
        display_name="Donor Case Manager",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Membership(
            id=uuid4(),
            organization_id=org_id,
            user_id=user.id,
            role=Role.CASE_MANAGER.value,
            is_active=True,
        )
    )
    db.add(
        RoleRecordScope(
            organization_id=org_id,
            role=Role.CASE_MANAGER.value,
            module="donors",
            assignment="all",
            phase="all",
        )
    )
    db.flush()
    return user


def _personal_workflow(db, org_id, owner_id, *, trigger_type, actions, trigger_config=None):
    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=org_id,
        name=f"Donor workflow {uuid4().hex[:6]}",
        subject_type="egg_donor",
        trigger_type=trigger_type,
        trigger_config=trigger_config or {},
        conditions=[],
        condition_logic="AND",
        actions=actions,
        scope="personal",
        owner_user_id=owner_id,
        is_enabled=True,
        created_by_user_id=owner_id,
        updated_by_user_id=owner_id,
    )
    db.add(workflow)
    db.flush()
    return workflow


def test_v2_donor_stage_regression_request_fails_action_without_stage_event(
    db, test_org, test_user
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.flush()
    owner = _case_manager(db, test_org.id)
    current = _stage(db, test_org.id, "pre_screening")
    target = _stage(db, test_org.id, "contacted")
    donor = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(
            donor_type="egg",
            full_name="Regression Donor",
            email=f"regression-{uuid4().hex[:8]}@example.com",
            owner_type="user",
            owner_id=owner.id,
        ),
    )
    donor.stage_id = current.id
    db.flush()

    regress = _personal_workflow(
        db,
        test_org.id,
        owner.id,
        trigger_type="donor_created",
        actions=[{"action_type": "update_field", "field": "stage_id", "value": str(target.id)}],
    )
    stage_listener = _personal_workflow(
        db,
        test_org.id,
        owner.id,
        trigger_type="donor_stage_changed",
        actions=[{"action_type": "add_note", "content": "Stage moved"}],
    )

    execution = engine.execute_workflow(
        db,
        regress,
        entity_type="donor",
        entity_id=donor.id,
        subject_type="egg_donor",
        subject_id=donor.id,
        event_data={"donor_id": str(donor.id)},
        source=WorkflowEventSource.USER,
    )

    assert execution is not None
    assert execution.actions_executed[0]["success"] is False, execution.actions_executed
    assert execution.actions_executed[0]["error"] == (
        "Workflow stage change requires regression approval"
    )
    db.refresh(donor)
    assert donor.stage_id == current.id
    request = (
        db.query(StatusChangeRequest)
        .filter_by(organization_id=test_org.id, entity_type="donor", entity_id=donor.id)
        .one()
    )
    assert (request.status, request.target_stage_id) == ("pending", target.id)
    assert request.requested_by_user_id == owner.id
    assert (
        db.query(WorkflowExecution)
        .filter_by(organization_id=test_org.id, workflow_id=stage_listener.id)
        .count()
        == 0
    )
