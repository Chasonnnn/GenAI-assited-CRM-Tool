"""Organization-scoped donor use cases."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, or_, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.encryption import hash_email, hash_phone
from app.db.enums import AuditEventType, DonorType, Role
from app.db.models import (
    Donor,
    DonorStatusHistory,
    Organization,
    Pipeline,
    PipelineStage,
    StatusChangeRequest,
)
from app.schemas.donor import DonorCreate, DonorUpdate
from app.services import (
    audit_service,
    dashboard_service,
    entity_activity_service,
    pipeline_semantics_service,
)
from app.utils.datetime_parsing import (
    normalize_effective_at,
    parse_created_from_filter,
    parse_created_to_filter,
)
from app.utils.normalization import (
    escape_like_string,
    normalize_email,
    normalize_phone,
)
from app.utils.pagination import paginate_query_by_offset

logger = logging.getLogger(__name__)


class DonorConflictError(ValueError):
    """A donor uniqueness rule was violated."""


class DonorValidationError(ValueError):
    """A donor domain invariant was violated."""


class DonorStatusChangeResult(TypedDict):
    status: Literal["applied", "pending_approval"]
    donor: Donor | None
    history: DonorStatusHistory | None
    request_id: UUID | None
    message: str | None


UNDO_GRACE_PERIOD = timedelta(minutes=5)


def _dispatch_side_effect_isolated(
    *,
    db: Session,
    donor: Donor,
    event_key: str,
    trigger: Callable[[Session, Donor], None],
    failure_kind: Literal["workflow", "notification"],
    details: dict | None = None,
) -> None:
    """Run a post-commit donor side effect without changing the mutation result."""
    from app.db.session import SessionLocal

    donor_id = donor.id
    organization_id = donor.organization_id
    donor_type = donor.donor_type
    bind = db.get_bind()
    side_effect_db = (
        Session(bind=bind, autoflush=False, join_transaction_mode="create_savepoint")
        if isinstance(bind, Connection)
        else SessionLocal()
    )
    try:
        side_effect_donor = get_donor(side_effect_db, organization_id, donor_id)
        if side_effect_donor is None:
            raise DonorValidationError("Donor unavailable for side-effect dispatch")
        trigger(side_effect_db, side_effect_donor)
    except Exception as exc:
        from app.db.enums import AlertSeverity, AlertType
        from app.services import alert_service

        error_message = (
            "Donor workflow trigger failed"
            if failure_kind == "workflow"
            else "Donor status request notification failed"
        )
        logger.error(
            error_message,
            extra={
                "donor_id": str(donor_id),
                "event_key": event_key,
                "error_class": type(exc).__name__,
            },
        )
        try:
            side_effect_db.rollback()
        except Exception:
            logger.error(
                "Donor side-effect transaction rollback failed",
                extra={"donor_id": str(donor_id), "event_key": event_key},
            )
        try:
            alert_service.record_alert_isolated(
                org_id=organization_id,
                alert_type=(
                    AlertType.WORKFLOW_EXECUTION_FAILED
                    if failure_kind == "workflow"
                    else AlertType.NOTIFICATION_PUSH_FAILED
                ),
                severity=AlertSeverity.ERROR,
                title=error_message,
                message=(
                    "A donor workflow trigger failed after the donor change was saved."
                    if failure_kind == "workflow"
                    else "A donor status request notification failed after the request change was saved."
                ),
                integration_key=(
                    f"donor_{event_key}"
                    if failure_kind == "workflow"
                    else f"donor_status_request_{event_key}"
                ),
                error_class=type(exc).__name__,
                details={
                    "donor_id": str(donor_id),
                    "donor_type": donor_type,
                    "event_key": event_key,
                    **(details or {}),
                },
            )
        except Exception:
            logger.error(
                "Donor side-effect failure alert could not be persisted",
                extra={"donor_id": str(donor_id), "event_key": event_key},
            )
    finally:
        side_effect_db.close()


def dispatch_stage_changed_workflow(
    db: Session,
    *,
    donor: Donor,
    old_stage: PipelineStage,
    new_stage: PipelineStage,
) -> None:
    from app.services import workflow_triggers

    old_stage_id = old_stage.id
    new_stage_id = new_stage.id

    def trigger(
        workflow_db: Session,
        workflow_donor: Donor,
    ) -> None:
        stages = {
            stage.id: stage
            for stage in workflow_db.query(PipelineStage)
            .join(Pipeline, PipelineStage.pipeline_id == Pipeline.id)
            .filter(
                PipelineStage.id.in_([old_stage_id, new_stage_id]),
                Pipeline.organization_id == workflow_donor.organization_id,
                Pipeline.entity_type == workflow_donor.pipeline_entity_type,
            )
            .all()
        }
        workflow_old_stage = stages.get(old_stage_id)
        workflow_new_stage = stages.get(new_stage_id)
        if workflow_old_stage is None or workflow_new_stage is None:
            raise DonorValidationError("Donor workflow stage unavailable")
        workflow_triggers.trigger_donor_stage_changed(
            workflow_db,
            workflow_donor,
            old_stage=workflow_old_stage,
            new_stage=workflow_new_stage,
        )

    _dispatch_side_effect_isolated(
        db=db,
        donor=donor,
        event_key="stage_changed",
        trigger=trigger,
        failure_kind="workflow",
        details={
            "old_stage_id": str(old_stage.id),
            "new_stage_id": str(new_stage.id),
        },
    )


def dispatch_status_request_pending_notification(
    db: Session,
    *,
    donor: Donor,
    status_request: StatusChangeRequest,
    target_stage_label: str,
    current_stage_label: str,
    requester_name: str,
) -> None:
    from app.services import notification_facade

    request_id = status_request.id

    def trigger(notification_db: Session, notification_donor: Donor) -> None:
        notification_request = (
            notification_db.query(StatusChangeRequest)
            .filter(
                StatusChangeRequest.id == request_id,
                StatusChangeRequest.organization_id == notification_donor.organization_id,
                StatusChangeRequest.entity_type == "donor",
                StatusChangeRequest.entity_id == notification_donor.id,
            )
            .first()
        )
        if notification_request is None:
            raise DonorValidationError("Donor status request unavailable for notification")
        notification_facade.notify_donor_status_change_request_pending(
            db=notification_db,
            request=notification_request,
            donor=notification_donor,
            target_stage_label=target_stage_label,
            current_stage_label=current_stage_label,
            requester_name=requester_name,
        )

    _dispatch_side_effect_isolated(
        db=db,
        donor=donor,
        event_key="pending",
        trigger=trigger,
        failure_kind="notification",
        details={"request_id": str(request_id)},
    )


def dispatch_status_request_resolved_notification(
    db: Session,
    *,
    donor: Donor,
    status_request: StatusChangeRequest,
    approved: bool,
    resolver_name: str,
    reason: str | None = None,
) -> None:
    from app.services import notification_facade

    request_id = status_request.id

    def trigger(notification_db: Session, notification_donor: Donor) -> None:
        notification_request = (
            notification_db.query(StatusChangeRequest)
            .filter(
                StatusChangeRequest.id == request_id,
                StatusChangeRequest.organization_id == notification_donor.organization_id,
                StatusChangeRequest.entity_type == "donor",
                StatusChangeRequest.entity_id == notification_donor.id,
            )
            .first()
        )
        if notification_request is None:
            raise DonorValidationError("Donor status request unavailable for notification")
        notification_facade.notify_donor_status_change_request_resolved(
            db=notification_db,
            request=notification_request,
            donor=notification_donor,
            approved=approved,
            resolver_name=resolver_name,
            reason=reason,
        )

    _dispatch_side_effect_isolated(
        db=db,
        donor=donor,
        event_key="approved" if approved else "rejected",
        trigger=trigger,
        failure_kind="notification",
        details={"request_id": str(request_id)},
    )


def _is_active_email_conflict(exc: IntegrityError) -> bool:
    diagnostic = getattr(exc.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None) == "uq_donors_active_email_hash"


def donor_pipeline_entity_type(donor_type: DonorType | str) -> str:
    value = donor_type.value if isinstance(donor_type, DonorType) else donor_type
    return f"{value}_donor"


def _get_org_timezone(db: Session, org_id: UUID) -> str:
    timezone = db.query(Organization.timezone).filter(Organization.id == org_id).scalar()
    return timezone or "America/Los_Angeles"


def generate_donor_number(db: Session, org_id: UUID) -> str:
    """Allocate the next organization-local D10001+ identifier atomically."""
    value = db.execute(
        text("""
            INSERT INTO org_counters (organization_id, counter_type, current_value)
            VALUES (:org_id, 'donor_number', 10001)
            ON CONFLICT (organization_id, counter_type)
            DO UPDATE SET current_value = org_counters.current_value + 1,
                          updated_at = now()
            RETURNING current_value
        """),
        {"org_id": org_id},
    ).scalar_one_or_none()
    if value is None:
        raise RuntimeError("Failed to generate donor number")
    return f"D{value:05d}"


def _validate_owner(
    db: Session,
    org_id: UUID,
    owner_type: str | None,
    owner_id: UUID | None,
) -> None:
    if owner_type is None and owner_id is None:
        return
    if owner_type is None or owner_id is None:
        raise DonorValidationError("owner_type and owner_id must be provided together")

    from app.services import task_service

    try:
        task_service.validate_task_owner(
            db,
            org_id,
            owner_type,
            owner_id,
            allow_none=False,
        )
    except ValueError as exc:
        raise DonorValidationError(str(exc)) from exc


def _get_default_pipeline(db: Session, org_id: UUID, donor_type: str) -> Pipeline:
    """Resolve the exact subtype pipeline without a fallback to another module."""
    entity_type = donor_pipeline_entity_type(donor_type)
    pipeline = (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == org_id,
            Pipeline.entity_type == entity_type,
            Pipeline.is_default.is_(True),
        )
        .first()
    )
    if pipeline is not None:
        return pipeline

    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type=entity_type,
    )
    if pipeline.entity_type != entity_type:
        raise DonorValidationError(f"Default {entity_type} pipeline is not configured")
    return pipeline


def _get_entry_stage(db: Session, pipeline: Pipeline) -> PipelineStage:
    from app.services import pipeline_service

    stage = pipeline_service.get_stage_by_system_role(
        db,
        pipeline.id,
        "intake_entry",
        entity_type=pipeline.entity_type,
    )
    if stage is None or not stage.is_active:
        raise DonorValidationError("Donor pipeline entry stage is not configured")
    return stage


def get_donor(db: Session, org_id: UUID, donor_id: UUID) -> Donor | None:
    return (
        db.query(Donor)
        .options(selectinload(Donor.stage))
        .filter(Donor.organization_id == org_id, Donor.id == donor_id)
        .first()
    )


def get_active_donor_by_email(db: Session, org_id: UUID, email: str) -> Donor | None:
    return (
        db.query(Donor)
        .filter(
            Donor.organization_id == org_id,
            Donor.email_hash == hash_email(normalize_email(email)),
            Donor.is_archived.is_(False),
        )
        .first()
    )


def list_donors(
    db: Session,
    org_id: UUID,
    *,
    donor_type: str | None = None,
    stage_id: UUID | None = None,
    state: str | None = None,
    q: str | None = None,
    owner_id: UUID | None = None,
    dynamic_filter: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    include_archived: bool = False,
    archived_only: bool = False,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Donor], int]:
    query = (
        db.query(Donor).options(selectinload(Donor.stage)).filter(Donor.organization_id == org_id)
    )
    if archived_only:
        query = query.filter(Donor.is_archived.is_(True))
    elif not include_archived:
        query = query.filter(Donor.is_archived.is_(False))
    if donor_type:
        query = query.filter(Donor.donor_type == donor_type)
    if stage_id:
        query = query.filter(Donor.stage_id == stage_id)
    if state:
        query = query.filter(Donor.state == state)
    if owner_id:
        query = query.filter(Donor.owner_id == owner_id)
    if created_from:
        try:
            query = query.filter(Donor.created_at >= parse_created_from_filter(created_from))
        except (TypeError, ValueError) as exc:
            raise DonorValidationError("Invalid created_from date") from exc
    if created_to:
        try:
            created_to_boundary, is_date_only = parse_created_to_filter(created_to)
        except (TypeError, ValueError) as exc:
            raise DonorValidationError("Invalid created_to date") from exc
        query = query.filter(
            Donor.created_at < created_to_boundary
            if is_date_only
            else Donor.created_at <= created_to_boundary
        )
    joined_stage = False
    if dynamic_filter:
        if dynamic_filter != "attention_stuck":
            raise DonorValidationError(f"Invalid dynamic_filter: {dynamic_filter}")
        latest_stage_change = (
            db.query(
                DonorStatusHistory.donor_id.label("donor_id"),
                func.max(DonorStatusHistory.effective_at).label("last_change_at"),
            )
            .filter(DonorStatusHistory.organization_id == org_id)
            .group_by(DonorStatusHistory.donor_id)
            .subquery()
        )
        last_change_at = func.coalesce(
            latest_stage_change.c.last_change_at,
            Donor.created_at,
        )
        query = (
            query.join(PipelineStage, Donor.stage_id == PipelineStage.id)
            .join(Pipeline, PipelineStage.pipeline_id == Pipeline.id)
            .outerjoin(
                latest_stage_change,
                latest_stage_change.c.donor_id == Donor.id,
            )
            .filter(
                *dashboard_service.attention_stuck_donor_stage_filters(org_id),
                last_change_at
                < datetime.now(UTC) - timedelta(days=dashboard_service.ATTENTION_STUCK_DAYS),
            )
        )
        joined_stage = True
    if q:
        escaped = escape_like_string(q.strip())
        filters = [
            Donor.full_name.ilike(f"%{escaped}%", escape="\\"),
            Donor.donor_number.ilike(f"%{escaped}%", escape="\\"),
        ]
        if "@" in q:
            try:
                filters.append(Donor.email_hash == hash_email(normalize_email(q)))
            except ValueError:
                pass
        try:
            normalized_phone = normalize_phone(q)
            if normalized_phone:
                filters.append(Donor.phone_hash == hash_phone(normalized_phone))
        except ValueError:
            pass
        query = query.filter(or_(*filters))

    sortable_columns = {
        "donor_number": Donor.donor_number,
        "full_name": func.lower(Donor.full_name),
        "state": func.lower(Donor.state),
        "education": func.lower(Donor.education),
        "created_at": Donor.created_at,
    }
    if sort_by == "stage":
        if not joined_stage:
            query = query.join(PipelineStage, Donor.stage_id == PipelineStage.id)
        sort_column = PipelineStage.order
    else:
        sort_column = sortable_columns.get(sort_by) if sort_by else None
    if sort_by and sort_column is None:
        raise DonorValidationError("Invalid donor sort column")
    if sort_order not in {"asc", "desc"}:
        raise DonorValidationError("Invalid donor sort order")
    if sort_column is not None:
        order_expression = (
            sort_column.asc().nullslast() if sort_order == "asc" else sort_column.desc().nullslast()
        )
        id_order = Donor.id.asc() if sort_order == "asc" else Donor.id.desc()
        query = query.order_by(order_expression, id_order)
    else:
        query = query.order_by(Donor.created_at.desc(), Donor.id.desc())
    offset = (page - 1) * per_page
    return paginate_query_by_offset(query, offset=offset, limit=per_page)


def create_donor(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    data: DonorCreate,
    request: Request | None = None,
    *,
    commit: bool = True,
    emit_workflow_events: bool = True,
) -> Donor:
    """Create the donor, initial history, and audit event atomically."""
    try:
        if get_active_donor_by_email(db, org_id, str(data.email)):
            raise DonorConflictError("An active donor with this email already exists")
        _validate_owner(db, org_id, data.owner_type, data.owner_id)

        pipeline = _get_default_pipeline(db, org_id, data.donor_type)
        stage = _get_entry_stage(db, pipeline)
        now = datetime.now(UTC)
        normalized_email = normalize_email(str(data.email))
        normalized_phone = normalize_phone(data.phone) if data.phone else None
        donor = Donor(
            organization_id=org_id,
            donor_number=generate_donor_number(db, org_id),
            donor_type=data.donor_type,
            full_name=data.full_name.strip(),
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            phone=normalized_phone,
            phone_hash=hash_phone(normalized_phone) if normalized_phone else None,
            state=data.state,
            education=data.education,
            source=data.source,
            owner_type=data.owner_type,
            owner_id=data.owner_id,
            stage_id=stage.id,
        )
        db.add(donor)
        db.flush()

        db.add(
            DonorStatusHistory(
                donor_id=donor.id,
                organization_id=org_id,
                changed_by_user_id=user_id,
                old_stage_id=None,
                new_stage_id=stage.id,
                old_status=None,
                new_status=stage.stage_key,
                old_label_snapshot=None,
                new_label_snapshot=stage.label,
                reason="Initial creation",
                effective_at=now,
                recorded_at=now,
            )
        )
        audit_service.log_event(
            db=db,
            org_id=org_id,
            event_type=AuditEventType.DONOR_CREATED,
            actor_user_id=user_id,
            target_type="donor",
            target_id=donor.id,
            details={
                "donor_type": donor.donor_type,
                "stage_id": str(stage.id),
                "owner_type": donor.owner_type,
                "owner_id": str(donor.owner_id) if donor.owner_id else None,
            },
            request=request,
        )
        entity_activity_service.record_activity(
            db,
            org_id=org_id,
            entity_type="donor",
            entity_id=donor.id,
            activity_type="record_created",
            actor_user_id=user_id,
            occurred_at=now,
        )
        if commit:
            db.commit()
        else:
            db.flush()
        refreshed = get_donor(db, org_id, donor.id) or donor
        if commit and emit_workflow_events:
            from app.services import workflow_triggers

            _dispatch_side_effect_isolated(
                db=db,
                donor=refreshed,
                event_key="created",
                failure_kind="workflow",
                trigger=lambda workflow_db, workflow_donor: workflow_triggers.trigger_donor_created(
                    workflow_db,
                    workflow_donor,
                ),
            )
        return refreshed
    except IntegrityError as exc:
        db.rollback()
        if _is_active_email_conflict(exc):
            raise DonorConflictError("An active donor with this email already exists") from exc
        raise
    except Exception:
        db.rollback()
        raise


def update_donor(
    db: Session,
    donor: Donor,
    user_id: UUID,
    data: DonorUpdate,
    request: Request | None = None,
    *,
    emit_workflow_events: bool = True,
) -> Donor:
    """Update mutable donor fields and audit in one transaction."""
    updates = data.model_dump(exclude_unset=True)
    old_owner_type = donor.owner_type
    old_owner_id = donor.owner_id
    try:
        if "email" in updates and updates["email"]:
            existing = get_active_donor_by_email(db, donor.organization_id, str(updates["email"]))
            if existing and existing.id != donor.id:
                raise DonorConflictError("An active donor with this email already exists")

        if "owner_type" in updates or "owner_id" in updates:
            next_owner_type = updates.get("owner_type", donor.owner_type)
            next_owner_id = updates.get("owner_id", donor.owner_id)
            _validate_owner(db, donor.organization_id, next_owner_type, next_owner_id)

        if "full_name" in updates and updates["full_name"]:
            donor.full_name = str(updates["full_name"]).strip()
        if "email" in updates and updates["email"]:
            normalized_email = normalize_email(str(updates["email"]))
            donor.email = normalized_email
            donor.email_hash = hash_email(normalized_email)
        if "phone" in updates:
            normalized_phone = normalize_phone(updates["phone"]) if updates["phone"] else None
            donor.phone = normalized_phone
            donor.phone_hash = hash_phone(normalized_phone) if normalized_phone else None
        for field in ("state", "education", "source", "owner_type", "owner_id"):
            if field in updates:
                setattr(donor, field, updates[field])
        donor.updated_at = datetime.now(UTC)

        audit_service.log_event(
            db=db,
            org_id=donor.organization_id,
            event_type=AuditEventType.DONOR_UPDATED,
            actor_user_id=user_id,
            target_type="donor",
            target_id=donor.id,
            details={"updated_fields": sorted(updates)},
            request=request,
        )
        entity_activity_service.record_activity(
            db,
            org_id=donor.organization_id,
            entity_type="donor",
            entity_id=donor.id,
            activity_type="info_edited",
            actor_user_id=user_id,
            details={"changed_fields": sorted(updates)},
            occurred_at=donor.updated_at,
        )
        if (old_owner_type, old_owner_id) != (donor.owner_type, donor.owner_id):
            entity_activity_service.record_activity(
                db,
                org_id=donor.organization_id,
                entity_type="donor",
                entity_id=donor.id,
                activity_type="assigned" if donor.owner_id else "unassigned",
                actor_user_id=user_id,
                details={
                    "from_owner_type": old_owner_type,
                    "from_owner_id": str(old_owner_id) if old_owner_id else None,
                    "to_owner_type": donor.owner_type,
                    "to_owner_id": str(donor.owner_id) if donor.owner_id else None,
                },
                occurred_at=donor.updated_at,
            )
        db.commit()
        refreshed = get_donor(db, donor.organization_id, donor.id) or donor
        if emit_workflow_events:
            from app.services import workflow_triggers

            if {"owner_type", "owner_id"} & updates.keys() and (
                old_owner_type != refreshed.owner_type or old_owner_id != refreshed.owner_id
            ):
                _dispatch_side_effect_isolated(
                    db=db,
                    donor=refreshed,
                    event_key="assigned",
                    failure_kind="workflow",
                    trigger=lambda workflow_db, workflow_donor: (
                        workflow_triggers.trigger_donor_assigned(
                            workflow_db,
                            workflow_donor,
                            old_owner_type=old_owner_type,
                            old_owner_id=old_owner_id,
                        )
                    ),
                    details={
                        "old_owner_type": old_owner_type,
                        "new_owner_type": refreshed.owner_type,
                    },
                )
            _dispatch_side_effect_isolated(
                db=db,
                donor=refreshed,
                event_key="updated",
                failure_kind="workflow",
                trigger=lambda workflow_db, workflow_donor: workflow_triggers.trigger_donor_updated(
                    workflow_db,
                    workflow_donor,
                    sorted(updates),
                ),
                details={"changed_fields": sorted(updates)},
            )
        return refreshed
    except IntegrityError as exc:
        db.rollback()
        if _is_active_email_conflict(exc):
            raise DonorConflictError("An active donor with this email already exists") from exc
        raise
    except Exception:
        db.rollback()
        raise


def archive_donor(
    db: Session,
    donor: Donor,
    user_id: UUID,
    request: Request | None = None,
) -> Donor:
    if donor.is_archived:
        raise DonorValidationError("Donor is already archived")
    try:
        stage = donor.stage
        now = datetime.now(UTC)
        donor.is_archived = True
        donor.archived_at = now
        donor.updated_at = now
        db.add(
            DonorStatusHistory(
                donor_id=donor.id,
                organization_id=donor.organization_id,
                changed_by_user_id=user_id,
                old_stage_id=stage.id,
                new_stage_id=stage.id,
                old_status=stage.stage_key,
                new_status=stage.stage_key,
                old_label_snapshot=stage.label,
                new_label_snapshot=stage.label,
                reason="Donor archived",
                effective_at=now,
                recorded_at=now,
            )
        )
        audit_service.log_event(
            db=db,
            org_id=donor.organization_id,
            event_type=AuditEventType.DONOR_ARCHIVED,
            actor_user_id=user_id,
            target_type="donor",
            target_id=donor.id,
            details={"donor_type": donor.donor_type},
            request=request,
        )
        entity_activity_service.record_activity(
            db,
            org_id=donor.organization_id,
            entity_type="donor",
            entity_id=donor.id,
            activity_type="archived",
            actor_user_id=user_id,
            occurred_at=now,
        )
        db.commit()
        return get_donor(db, donor.organization_id, donor.id) or donor
    except Exception:
        db.rollback()
        raise


def restore_donor(
    db: Session,
    donor: Donor,
    user_id: UUID,
    request: Request | None = None,
) -> Donor:
    """Restore an archived donor when its active email identity is available."""
    if not donor.is_archived:
        raise DonorValidationError("Donor is not archived")
    try:
        existing = get_active_donor_by_email(db, donor.organization_id, donor.email)
        if existing is not None and existing.id != donor.id:
            raise DonorConflictError("An active donor with this email already exists")
        stage = donor.stage
        now = datetime.now(UTC)
        donor.is_archived = False
        donor.archived_at = None
        donor.updated_at = now
        db.add(
            DonorStatusHistory(
                donor_id=donor.id,
                organization_id=donor.organization_id,
                changed_by_user_id=user_id,
                old_stage_id=stage.id,
                new_stage_id=stage.id,
                old_status=stage.stage_key,
                new_status=stage.stage_key,
                old_label_snapshot=stage.label,
                new_label_snapshot=stage.label,
                reason="Donor restored",
                effective_at=now,
                recorded_at=now,
            )
        )
        audit_service.log_event(
            db=db,
            org_id=donor.organization_id,
            event_type=AuditEventType.DONOR_RESTORED,
            actor_user_id=user_id,
            target_type="donor",
            target_id=donor.id,
            details={"donor_type": donor.donor_type},
            request=request,
        )
        entity_activity_service.record_activity(
            db,
            org_id=donor.organization_id,
            entity_type="donor",
            entity_id=donor.id,
            activity_type="restored",
            actor_user_id=user_id,
            occurred_at=now,
        )
        db.commit()
        return get_donor(db, donor.organization_id, donor.id) or donor
    except IntegrityError as exc:
        db.rollback()
        if _is_active_email_conflict(exc):
            raise DonorConflictError("An active donor with this email already exists") from exc
        raise
    except Exception:
        db.rollback()
        raise


def change_status(
    db: Session,
    donor: Donor,
    stage_id: UUID,
    user_id: UUID,
    reason: str | None = None,
    effective_at: datetime | None = None,
    request: Request | None = None,
    *,
    user_role: Role | str | None = None,
    emit_workflow_events: bool = True,
) -> DonorStatusChangeResult:
    if donor.is_archived:
        raise DonorValidationError("Cannot change status of an archived donor")

    entity_type = donor_pipeline_entity_type(donor.donor_type)
    target = (
        db.query(PipelineStage)
        .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
        .filter(
            PipelineStage.id == stage_id,
            PipelineStage.is_active.is_(True),
            Pipeline.organization_id == donor.organization_id,
            Pipeline.entity_type == entity_type,
            Pipeline.is_default.is_(True),
        )
        .first()
    )
    if target is None:
        raise DonorValidationError("Target stage not found in donor pipeline")
    if target.id == donor.stage_id:
        raise DonorValidationError("Target stage is the current donor stage")

    role_value = user_role.value if isinstance(user_role, Role) else user_role
    if not role_value:
        raise DonorValidationError("User role is required to change donor stage")
    feature_config = pipeline_semantics_service.get_pipeline_feature_config(target.pipeline)
    if not pipeline_semantics_service.can_role_access_stage(
        role_value,
        target,
        feature_config=feature_config,
        mutation=True,
    ):
        raise DonorValidationError("Role not permitted to change donor stage")
    target_semantics = pipeline_semantics_service.get_stage_semantics(target)
    normalized_reason = reason.strip() if reason else None
    if target_semantics.requires_reason_on_enter and not normalized_reason:
        raise DonorValidationError("Reason required for this stage")

    old_stage = donor.stage
    now = datetime.now(UTC)
    normalized_effective_at = normalize_effective_at(
        effective_at,
        _get_org_timezone(db, donor.organization_id),
    )
    is_backdated = (now - normalized_effective_at).total_seconds() > 1
    is_regression = target.order < old_stage.order

    if (normalized_effective_at - now).total_seconds() > 1:
        raise DonorValidationError("Cannot set future date for donor stage change")
    if donor.created_at and normalized_effective_at < donor.created_at:
        raise DonorValidationError("Cannot set date before donor was created")

    if is_regression:
        last_history = (
            db.query(DonorStatusHistory)
            .filter(DonorStatusHistory.donor_id == donor.id)
            .order_by(DonorStatusHistory.recorded_at.desc())
            .first()
        )
        within_grace_period = bool(
            last_history
            and last_history.changed_by_user_id == user_id
            and last_history.recorded_at
            and (now - last_history.recorded_at) <= UNDO_GRACE_PERIOD
            and last_history.old_stage_id == target.id
            and last_history.new_stage_id == old_stage.id
        )
        if within_grace_period:
            return apply_status_change(
                db,
                donor=donor,
                old_stage=old_stage,
                new_stage=target,
                user_id=user_id,
                reason=normalized_reason,
                effective_at=normalized_effective_at,
                recorded_at=now,
                request=request,
                is_undo=True,
                emit_workflow_events=emit_workflow_events,
            )

    if (is_backdated or is_regression) and not normalized_reason:
        raise DonorValidationError("Reason required for backdated or regressed stage changes")

    if is_regression and role_value not in {Role.ADMIN.value, Role.DEVELOPER.value}:
        status_request = StatusChangeRequest(
            organization_id=donor.organization_id,
            entity_type="donor",
            entity_id=donor.id,
            target_stage_id=target.id,
            effective_at=normalized_effective_at,
            reason=normalized_reason or "",
            requested_by_user_id=user_id,
            requested_at=now,
            status="pending",
        )
        db.add(status_request)
        db.flush()
        from app.services import entity_activity_service

        entity_activity_service.record_activity(
            db,
            org_id=donor.organization_id,
            entity_type="donor",
            entity_id=donor.id,
            activity_type="status_change_requested",
            actor_user_id=user_id,
            details={
                "status_request_id": str(status_request.id),
                "target_stage_id": str(target.id),
            },
            occurred_at=now,
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise DonorValidationError(
                "A pending donor regression request already exists for this stage and date."
            ) from exc
        db.refresh(status_request)
        from app.services import membership_service

        requester_membership = membership_service.get_membership_for_org(
            db,
            donor.organization_id,
            user_id,
        )
        requester_name = (
            requester_membership.user.display_name
            if requester_membership and requester_membership.user
            else "Someone"
        )
        dispatch_status_request_pending_notification(
            db,
            donor=donor,
            status_request=status_request,
            target_stage_label=target.label,
            current_stage_label=old_stage.label,
            requester_name=requester_name,
        )
        return DonorStatusChangeResult(
            status="pending_approval",
            donor=donor,
            history=None,
            request_id=status_request.id,
            message="Regression requires admin approval. Request submitted.",
        )

    return apply_status_change(
        db,
        donor=donor,
        old_stage=old_stage,
        new_stage=target,
        user_id=user_id,
        reason=normalized_reason,
        effective_at=normalized_effective_at,
        recorded_at=now,
        request=request,
        approved_by_user_id=user_id if is_regression else None,
        approved_at=now if is_regression else None,
        emit_workflow_events=emit_workflow_events,
    )


def apply_status_change(
    db: Session,
    *,
    donor: Donor,
    old_stage: PipelineStage,
    new_stage: PipelineStage,
    user_id: UUID | None,
    reason: str | None,
    effective_at: datetime,
    recorded_at: datetime,
    request: Request | None = None,
    is_undo: bool = False,
    request_id: UUID | None = None,
    requested_at: datetime | None = None,
    approved_by_user_id: UUID | None = None,
    approved_at: datetime | None = None,
    emit_workflow_events: bool = True,
    commit: bool = True,
) -> DonorStatusChangeResult:
    try:
        history = DonorStatusHistory(
            donor_id=donor.id,
            organization_id=donor.organization_id,
            changed_by_user_id=user_id,
            old_stage_id=old_stage.id,
            new_stage_id=new_stage.id,
            old_status=old_stage.stage_key,
            new_status=new_stage.stage_key,
            old_label_snapshot=old_stage.label,
            new_label_snapshot=new_stage.label,
            reason=reason,
            effective_at=effective_at,
            recorded_at=recorded_at,
            is_undo=is_undo,
            request_id=request_id,
            requested_at=requested_at,
            approved_by_user_id=approved_by_user_id,
            approved_at=approved_at,
        )
        donor.stage_id = new_stage.id
        donor.stage = new_stage
        donor.updated_at = recorded_at
        db.add(history)
        db.flush()
        audit_service.log_event(
            db=db,
            org_id=donor.organization_id,
            event_type=AuditEventType.DONOR_STATUS_CHANGED,
            actor_user_id=user_id,
            target_type="donor",
            target_id=donor.id,
            details={
                "donor_type": donor.donor_type,
                "from_stage_id": str(old_stage.id),
                "to_stage_id": str(new_stage.id),
                "request_id": str(request_id) if request_id else None,
            },
            request=request,
        )
        if commit:
            db.commit()
            refreshed = get_donor(db, donor.organization_id, donor.id) or donor
            db.refresh(history)
        else:
            db.flush()
            refreshed = donor
    except Exception:
        db.rollback()
        raise

    if emit_workflow_events and commit:
        dispatch_stage_changed_workflow(
            db,
            donor=refreshed,
            old_stage=old_stage,
            new_stage=new_stage,
        )

    return DonorStatusChangeResult(
        status="applied",
        donor=refreshed,
        history=history,
        request_id=None,
        message=None,
    )


def get_status_history(db: Session, org_id: UUID, donor_id: UUID) -> list[DonorStatusHistory]:
    return (
        db.query(DonorStatusHistory)
        .filter(
            DonorStatusHistory.organization_id == org_id,
            DonorStatusHistory.donor_id == donor_id,
        )
        .order_by(DonorStatusHistory.recorded_at.desc())
        .all()
    )
