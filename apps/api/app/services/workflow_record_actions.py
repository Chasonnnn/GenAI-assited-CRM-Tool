"""Workflow record mutations with existing domain transactions and event provenance."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID
from app.db.enums import EntityType, OwnerType, WorkflowEventSource, WorkflowTriggerType
from app.db.models import Donor, Surrogate, WorkflowExecution
from app.schemas.workflow import ALLOWED_UPDATE_FIELDS, DONOR_ALLOWED_UPDATE_FIELDS

TriggerCallback = Callable[..., list[WorkflowExecution]]


def assign_donor(
    db: Session,
    action: dict,
    entity: Donor,
    event_id: UUID,
    depth: int,
    trigger_callback: TriggerCallback | None,
) -> dict:
    """Assign a donor through the donor use-case boundary."""
    from app.schemas.donor import DonorUpdate
    from app.services import donor_service

    owner_type = action.get("owner_type")
    owner_id = action.get("owner_id")
    resolved_owner_id = UUID(owner_id) if isinstance(owner_id, str) else owner_id
    old_owner_type = entity.owner_type
    old_owner_id = entity.owner_id
    updated = donor_service.update_donor(
        db,
        entity,
        SYSTEM_USER_ID,
        DonorUpdate(owner_type=owner_type, owner_id=resolved_owner_id),
        emit_workflow_events=False,
    )

    if trigger_callback and (
        old_owner_type != updated.owner_type or old_owner_id != updated.owner_id
    ):
        trigger_callback(
            db=db,
            trigger_type=WorkflowTriggerType.DONOR_ASSIGNED,
            entity_type="donor",
            entity_id=updated.id,
            subject_type=updated.pipeline_entity_type,
            subject_id=updated.id,
            event_data={
                "donor_id": str(updated.id),
                "old_owner_type": old_owner_type,
                "old_owner_id": str(old_owner_id) if old_owner_id else None,
                "new_owner_type": updated.owner_type,
                "new_owner_id": str(updated.owner_id) if updated.owner_id else None,
            },
            org_id=updated.organization_id,
            event_id=event_id,
            depth=depth + 1,
            source=WorkflowEventSource.WORKFLOW,
            entity_owner_id=(
                updated.owner_id if updated.owner_type == OwnerType.USER.value else None
            ),
        )

    return {
        "success": True,
        "description": f"Assigned donor to {owner_type}:{resolved_owner_id}",
    }


def assign_surrogate(
    db: Session,
    action: dict,
    entity: Surrogate,
    event_id: UUID,
    depth: int,
    trigger_callback: TriggerCallback | None,
) -> dict:
    """Assign surrogate to user or queue."""
    owner_type = action.get("owner_type")
    owner_id = action.get("owner_id")

    old_owner_type = entity.owner_type
    old_owner_id = entity.owner_id

    entity.owner_type = owner_type
    entity.owner_id = UUID(owner_id) if isinstance(owner_id, str) else owner_id
    entity.updated_at = datetime.now(UTC)

    db.commit()

    # Trigger surrogate_assigned workflow (with increased depth to prevent loops)
    if trigger_callback:
        trigger_callback(
            db=db,
            trigger_type=WorkflowTriggerType.SURROGATE_ASSIGNED,
            entity_type="surrogate",
            entity_id=entity.id,
            event_data={
                "old_owner_type": old_owner_type,
                "old_owner_id": str(old_owner_id) if old_owner_id else None,
                "new_owner_type": owner_type,
                "new_owner_id": str(owner_id),
            },
            org_id=entity.organization_id,
            event_id=event_id,
            depth=depth + 1,
            source=WorkflowEventSource.WORKFLOW,
        )

    return {
        "success": True,
        "description": f"Assigned surrogate to {owner_type}:{owner_id}",
    }


def update_field(
    db: Session,
    action: dict,
    entity: Surrogate | Donor,
    event_id: UUID,
    depth: int,
    trigger_callback: TriggerCallback | None,
    *,
    workflow_actor_id: UUID | None = None,
    execution_permissions: frozenset[str] | None = None,
    v2_authority: bool = False,
) -> dict:
    """Update an allowlisted subject field."""
    from app.db.models import SurrogateStatusHistory
    from app.services import pipeline_service

    field = action.get("field")
    value = action.get("value")

    if isinstance(entity, Donor):
        if field not in DONOR_ALLOWED_UPDATE_FIELDS:
            return {"success": False, "error": f"Field {field} not allowed for donor update"}
        from app.schemas.donor import DonorUpdate
        from app.services import donor_service

        old_value = getattr(entity, field, None)
        if field == "stage_id":
            from app.db.enums import Role

            new_stage_id = UUID(value) if isinstance(value, str) else value
            if new_stage_id == entity.stage_id:
                return {"success": True, "description": "Stage unchanged"}
            old_stage = entity.stage
            from app.services.workflow_execution_authority import active_session

            actor_session = (
                active_session(db, entity.organization_id, workflow_actor_id)
                if v2_authority and execution_permissions is None
                else None
            )
            result = donor_service.change_status(
                db,
                entity,
                new_stage_id,
                workflow_actor_id if v2_authority else SYSTEM_USER_ID,
                reason="Workflow update",
                user_role=actor_session.role if actor_session else Role.DEVELOPER,
                emit_workflow_events=False,
                **({"execution_permissions": execution_permissions} if v2_authority else {}),
            )
            updated = result["donor"]
            if updated is None:
                return {"success": False, "error": "Donor stage change was not applied"}
            if trigger_callback:
                trigger_callback(
                    db=db,
                    trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED,
                    entity_type="donor",
                    entity_id=updated.id,
                    subject_type=updated.pipeline_entity_type,
                    subject_id=updated.id,
                    event_data={
                        "donor_id": str(updated.id),
                        "old_stage_id": str(old_stage.id),
                        "new_stage_id": str(updated.stage.id),
                        "old_stage_key": old_stage.stage_key,
                        "new_stage_key": updated.stage.stage_key,
                        "old_status": old_stage.slug,
                        "new_status": updated.stage.slug,
                    },
                    org_id=updated.organization_id,
                    event_id=event_id,
                    depth=depth + 1,
                    source=WorkflowEventSource.WORKFLOW,
                    entity_owner_id=(
                        updated.owner_id if updated.owner_type == OwnerType.USER.value else None
                    ),
                )
        else:
            updated = donor_service.update_donor(
                db,
                entity,
                SYSTEM_USER_ID,
                DonorUpdate(**{field: value}),
                emit_workflow_events=False,
            )
            if trigger_callback:
                trigger_callback(
                    db=db,
                    trigger_type=WorkflowTriggerType.DONOR_UPDATED,
                    entity_type="donor",
                    entity_id=updated.id,
                    subject_type=updated.pipeline_entity_type,
                    subject_id=updated.id,
                    event_data={
                        "donor_id": str(updated.id),
                        "changed_fields": [field],
                    },
                    org_id=updated.organization_id,
                    event_id=event_id,
                    depth=depth + 1,
                    source=WorkflowEventSource.WORKFLOW,
                    entity_owner_id=(
                        updated.owner_id if updated.owner_type == OwnerType.USER.value else None
                    ),
                )
        return {
            "success": True,
            "description": f"Updated {field} from {old_value} to {value}",
        }

    if field not in ALLOWED_UPDATE_FIELDS:
        return {"success": False, "error": f"Field {field} not allowed for update"}

    old_value = getattr(entity, field, None)

    if field == "stage_id":
        new_stage_id = UUID(value) if isinstance(value, str) else value
        if new_stage_id == entity.stage_id:
            return {"success": True, "description": "Stage unchanged"}

        stage = pipeline_service.get_stage_by_id(db, new_stage_id)
        current_stage = (
            pipeline_service.get_stage_by_id(db, entity.stage_id) if entity.stage_id else None
        )
        surrogate_pipeline_id = current_stage.pipeline_id if current_stage else None
        if not surrogate_pipeline_id:
            surrogate_pipeline_id = pipeline_service.get_or_create_default_pipeline(
                db,
                entity.organization_id,
            ).id
        if not stage or not stage.is_active or stage.pipeline_id != surrogate_pipeline_id:
            return {"success": False, "error": "Invalid stage for surrogate pipeline"}

        old_stage_id = entity.stage_id
        old_label = entity.status_label
        old_stage = pipeline_service.get_stage_by_id(db, old_stage_id) if old_stage_id else None
        old_slug = old_stage.slug if old_stage else None
        old_stage_key = old_stage.stage_key if old_stage else None
        if v2_authority:
            from app.services import surrogate_status_service
            from app.services.workflow_execution_authority import active_session

            actor_session = (
                active_session(db, entity.organization_id, workflow_actor_id)
                if execution_permissions is None
                else None
            )
            from app.db.enums import Role

            result = surrogate_status_service.change_status(
                db,
                entity,
                stage.id,
                workflow_actor_id,
                actor_session.role if actor_session else Role.DEVELOPER,
                reason="Workflow update",
                trigger_workflows=False,
                execution_permissions=execution_permissions,
            )
            if result.status != "applied":
                return {
                    "success": False,
                    "error": "Workflow stage change requires regression approval",
                }
        else:
            entity.stage_id = stage.id
            entity.status_label = stage.label
            entity.updated_at = datetime.now(UTC)

            history = SurrogateStatusHistory(
                surrogate_id=entity.id,
                organization_id=entity.organization_id,
                from_stage_id=old_stage_id,
                to_stage_id=stage.id,
                from_label_snapshot=old_label,
                to_label_snapshot=stage.label,
                changed_by_user_id=None,
                reason="Workflow update",
            )
            db.add(history)
            db.commit()

        # Trigger status_changed workflow with loop protection
        if trigger_callback:
            trigger_callback(
                db=db,
                trigger_type=WorkflowTriggerType.STATUS_CHANGED,
                entity_type="surrogate",
                entity_id=entity.id,
                event_data={
                    "surrogate_id": str(entity.id),
                    "old_stage_id": str(old_stage_id) if old_stage_id else None,
                    "new_stage_id": str(stage.id),
                    "old_stage_key": old_stage_key,
                    "new_stage_key": stage.stage_key,
                    "old_status": old_slug,
                    "new_status": stage.slug,
                },
                org_id=entity.organization_id,
                event_id=event_id,
                depth=depth + 1,
                source=WorkflowEventSource.WORKFLOW,
            )
    else:
        setattr(entity, field, value)
        entity.updated_at = datetime.now(UTC)
        db.commit()

    # Trigger surrogate_updated workflow
    if trigger_callback:
        trigger_callback(
            db=db,
            trigger_type=WorkflowTriggerType.SURROGATE_UPDATED,
            entity_type="surrogate",
            entity_id=entity.id,
            event_data={
                "changed_fields": [field],
                "old_values": {field: str(old_value) if old_value is not None else None},
                "new_values": {field: str(value)},
            },
            org_id=entity.organization_id,
            event_id=event_id,
            depth=depth + 1,
            source=WorkflowEventSource.WORKFLOW,
        )

    return {
        "success": True,
        "description": f"Updated {field} to {value}",
    }


def add_note(
    db: Session,
    action: dict,
    entity: Surrogate | Donor,
    workflow_actor_id: UUID | None = None,
    use_workflow_actor: bool = False,
) -> dict:
    """Add a note to a surrogate or donor subject."""
    content = action.get("content", "")

    # Determine author (prefer owner, fall back to creator)
    author_id = workflow_actor_id if use_workflow_actor else None
    if author_id:
        pass
    elif entity.owner_type == OwnerType.USER.value and entity.owner_id:
        author_id = entity.owner_id
    elif getattr(entity, "created_by_user_id", None):
        author_id = entity.created_by_user_id
    elif workflow_actor_id:
        author_id = workflow_actor_id

    if not author_id:
        return {
            "success": False,
            "error": "No user available to author note",
        }

    from app.services import note_service

    note = note_service.create_note(
        db,
        org_id=entity.organization_id,
        entity_type=(
            EntityType.DONOR.value if isinstance(entity, Donor) else EntityType.SURROGATE.value
        ),
        entity_id=entity.id,
        content=content,
        author_id=author_id,
        commit=False,
        emit_events=False,
    )

    return {
        "success": True,
        "note_id": str(note.id),
        "description": "Added note",
    }
