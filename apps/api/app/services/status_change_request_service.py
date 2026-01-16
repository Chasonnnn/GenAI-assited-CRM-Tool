"""Service for handling status change requests (admin approval workflow)."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import Role
from app.db.models import (
    StatusChangeRequest,
    Surrogate,
    User,
    PipelineStage,
    IntendedParent,
)


def get_request(db: Session, request_id: UUID, org_id: UUID) -> StatusChangeRequest | None:
    """Get a status change request by ID."""
    return (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.id == request_id,
            StatusChangeRequest.organization_id == org_id,
        )
        .first()
    )


def get_pending_requests(
    db: Session,
    org_id: UUID,
    entity_type: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[StatusChangeRequest], int]:
    """
    Get pending status change requests for an organization.

    Args:
        org_id: Organization ID
        entity_type: Optional filter by entity type ('surrogate' or 'intended_parent')
        page: Page number
        per_page: Items per page

    Returns:
        (requests, total_count)
    """
    query = db.query(StatusChangeRequest).filter(
        StatusChangeRequest.organization_id == org_id,
        StatusChangeRequest.status == "pending",
    )

    if entity_type:
        query = query.filter(StatusChangeRequest.entity_type == entity_type)

    total = query.count()
    offset = (page - 1) * per_page
    requests = (
        query.order_by(StatusChangeRequest.requested_at.desc()).offset(offset).limit(per_page).all()
    )

    return requests, total


def approve_request(
    db: Session,
    request_id: UUID,
    org_id: UUID,
    admin_user_id: UUID,
    admin_role: Role | None = None,
) -> StatusChangeRequest:
    """
    Approve a pending status change request.

    Applies the stage/status change to the entity and records audit trail.

    Args:
        db: Database session
        request_id: Request ID to approve
        admin_user_id: User ID of the approving admin
        admin_role: Role of the approving admin (must be admin or developer)

    Returns:
        Updated StatusChangeRequest

    Raises:
        ValueError: If request not found, not pending, or user not authorized
    """
    from app.services import surrogate_service, pipeline_service, ip_service

    request = get_request(db, request_id, org_id)
    if not request:
        raise ValueError("Request not found")

    if request.status != "pending":
        raise ValueError(f"Request is not pending (status: {request.status})")

    # Check admin permission
    role_str = admin_role.value if hasattr(admin_role, "value") else admin_role
    if role_str not in [Role.ADMIN.value, Role.DEVELOPER.value]:
        raise ValueError("Only admins can approve status change requests")

    now = datetime.now(timezone.utc)

    if request.entity_type == "surrogate":
        # Get surrogate
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.id == request.entity_id,
                Surrogate.organization_id == org_id,
            )
            .first()
        )
        if not surrogate:
            raise ValueError("Surrogate not found")

        # Get target stage
        new_stage = pipeline_service.get_stage_by_id(db, request.target_stage_id)
        if not new_stage:
            raise ValueError("Target stage not found")

        old_stage_id = surrogate.stage_id
        old_label = surrogate.status_label
        old_stage = pipeline_service.get_stage_by_id(db, old_stage_id) if old_stage_id else None
        old_slug = old_stage.slug if old_stage else None

        # Apply the change using the helper function
        surrogate_service._apply_status_change(
            db=db,
            surrogate=surrogate,
            new_stage=new_stage,
            old_stage_id=old_stage_id,
            old_label=old_label,
            old_slug=old_slug,
            user_id=request.requested_by_user_id,
            reason=request.reason,
            effective_at=request.effective_at,
            recorded_at=now,
            is_undo=False,
            request_id=request.id,
            approved_by_user_id=admin_user_id,
            approved_at=now,
            requested_at=request.requested_at,
        )

    elif request.entity_type == "intended_parent":
        intended_parent = (
            db.query(IntendedParent)
            .filter(
                IntendedParent.id == request.entity_id,
                IntendedParent.organization_id == org_id,
            )
            .first()
        )
        if not intended_parent:
            raise ValueError("Intended parent not found")
        if not request.target_status:
            raise ValueError("Target status not found")

        old_status = intended_parent.status
        ip_service._apply_status_change(
            db=db,
            ip=intended_parent,
            new_status=request.target_status,
            old_status=old_status,
            user_id=request.requested_by_user_id,
            reason=request.reason,
            effective_at=request.effective_at,
            recorded_at=now,
            is_undo=False,
            request_id=request.id,
            approved_by_user_id=admin_user_id,
            approved_at=now,
            requested_at=request.requested_at,
        )
    else:
        raise ValueError(f"Unknown entity type: {request.entity_type}")

    # Update request status
    request.status = "approved"
    request.approved_by_user_id = admin_user_id
    request.approved_at = now

    db.commit()
    db.refresh(request)

    from app.services import notification_service

    if request.entity_type == "surrogate":
        admin_user = db.query(User).filter(User.id == admin_user_id).first()
        resolver_name = admin_user.display_name if admin_user else "Admin"
        notification_service.notify_status_change_request_resolved(
            db=db,
            request=request,
            surrogate=surrogate,
            approved=True,
            resolver_name=resolver_name,
        )
    elif request.entity_type == "intended_parent":
        admin_user = db.query(User).filter(User.id == admin_user_id).first()
        resolver_name = admin_user.display_name if admin_user else "Admin"
        notification_service.notify_ip_status_change_request_resolved(
            db=db,
            request=request,
            intended_parent=intended_parent,
            approved=True,
            resolver_name=resolver_name,
        )

    return request


def reject_request(
    db: Session,
    request_id: UUID,
    org_id: UUID,
    admin_user_id: UUID,
    admin_role: Role | None = None,
    reason: str | None = None,
) -> StatusChangeRequest:
    """
    Reject a pending status change request.

    Args:
        db: Database session
        request_id: Request ID to reject
        admin_user_id: User ID of the rejecting admin
        admin_role: Role of the rejecting admin (must be admin or developer)
        reason: Optional rejection reason

    Returns:
        Updated StatusChangeRequest

    Raises:
        ValueError: If request not found, not pending, or user not authorized
    """
    request = get_request(db, request_id, org_id)
    if not request:
        raise ValueError("Request not found")

    if request.status != "pending":
        raise ValueError(f"Request is not pending (status: {request.status})")

    # Check admin permission
    role_str = admin_role.value if hasattr(admin_role, "value") else admin_role
    if role_str not in [Role.ADMIN.value, Role.DEVELOPER.value]:
        raise ValueError("Only admins can reject status change requests")

    now = datetime.now(timezone.utc)

    request.status = "rejected"
    request.rejected_by_user_id = admin_user_id
    request.rejected_at = now

    db.commit()
    db.refresh(request)

    if request.entity_type == "surrogate":
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.id == request.entity_id,
                Surrogate.organization_id == org_id,
            )
            .first()
        )
        if surrogate:
            from app.services import notification_service

            admin_user = db.query(User).filter(User.id == admin_user_id).first()
            resolver_name = admin_user.display_name if admin_user else "Admin"
            notification_service.notify_status_change_request_resolved(
                db=db,
                request=request,
                surrogate=surrogate,
                approved=False,
                resolver_name=resolver_name,
                reason=reason,
            )
    elif request.entity_type == "intended_parent":
        intended_parent = (
            db.query(IntendedParent)
            .filter(
                IntendedParent.id == request.entity_id,
                IntendedParent.organization_id == org_id,
            )
            .first()
        )
        if intended_parent:
            from app.services import notification_service

            admin_user = db.query(User).filter(User.id == admin_user_id).first()
            resolver_name = admin_user.display_name if admin_user else "Admin"
            notification_service.notify_ip_status_change_request_resolved(
                db=db,
                request=request,
                intended_parent=intended_parent,
                approved=False,
                resolver_name=resolver_name,
                reason=reason,
            )

    return request


def cancel_request(
    db: Session,
    request_id: UUID,
    org_id: UUID,
    user_id: UUID,
) -> StatusChangeRequest:
    """
    Cancel a pending status change request.

    Only the requester can cancel their own request.

    Args:
        db: Database session
        request_id: Request ID to cancel
        user_id: User ID of the requester

    Returns:
        Updated StatusChangeRequest

    Raises:
        ValueError: If request not found, not pending, or user not the requester
    """
    request = get_request(db, request_id, org_id)
    if not request:
        raise ValueError("Request not found")

    if request.status != "pending":
        raise ValueError(f"Request is not pending (status: {request.status})")

    if request.requested_by_user_id != user_id:
        raise ValueError("Only the requester can cancel their request")

    now = datetime.now(timezone.utc)

    request.status = "cancelled"
    request.cancelled_by_user_id = user_id
    request.cancelled_at = now

    db.commit()
    db.refresh(request)

    return request


def get_request_with_details(
    db: Session,
    request_id: UUID,
    org_id: UUID,
) -> dict | None:
    """
    Get a status change request with related entity and user details.

    Returns dict with:
    - request: StatusChangeRequest
    - entity_name: Name of the entity (surrogate name or IP name)
    - entity_number: Entity number (S#### or I####)
    - requester_name: Name of the user who requested
    - target_stage_label: Label of the target stage/status
    - current_stage_label: Label of the current stage/status
    """
    request = get_request(db, request_id, org_id)
    if not request:
        return None

    result = {
        "request": request,
        "entity_name": None,
        "entity_number": None,
        "requester_name": None,
        "target_stage_label": None,
        "current_stage_label": None,
    }

    # Get requester name
    requester = db.query(User).filter(User.id == request.requested_by_user_id).first()
    if requester:
        result["requester_name"] = requester.display_name

    if request.entity_type == "surrogate":
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.id == request.entity_id,
                Surrogate.organization_id == org_id,
            )
            .first()
        )
        if surrogate:
            result["entity_name"] = surrogate.full_name
            result["entity_number"] = surrogate.surrogate_number
            result["current_stage_label"] = surrogate.status_label

            # Get target stage label
            if request.target_stage_id:
                target_stage = (
                    db.query(PipelineStage)
                    .filter(PipelineStage.id == request.target_stage_id)
                    .first()
                )
                if target_stage:
                    result["target_stage_label"] = target_stage.label
    elif request.entity_type == "intended_parent":
        intended_parent = (
            db.query(IntendedParent)
            .filter(
                IntendedParent.id == request.entity_id,
                IntendedParent.organization_id == org_id,
            )
            .first()
        )
        if intended_parent:
            result["entity_name"] = intended_parent.full_name
            result["entity_number"] = intended_parent.intended_parent_number
            result["current_stage_label"] = _format_status_label(intended_parent.status)
            if request.target_status:
                result["target_stage_label"] = _format_status_label(request.target_status)

    return result


def _format_status_label(status: str | None) -> str:
    if not status:
        return "Unknown"
    return status.replace("_", " ").title()
