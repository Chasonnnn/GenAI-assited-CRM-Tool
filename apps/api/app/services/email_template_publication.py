"""Publish independent organization templates within the caller's transaction."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import AuditEventType, Role
from app.db.models import EmailTemplate, Membership, Organization, User
from app.services import audit_service, permission_service


def publish_template_to_org(
    db: Session,
    *,
    org_id: UUID,
    template_id: UUID,
    actor_user_id: UUID,
    name: str | None = None,
) -> EmailTemplate:
    db.query(Organization).filter(Organization.id == org_id).with_for_update().one()
    source = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == template_id,
            EmailTemplate.organization_id == org_id,
            EmailTemplate.is_active.is_(True),
        )
        .populate_existing()
        .first()
    )
    if source is None:
        raise LookupError("Template not found")
    membership = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == org_id,
            Membership.user_id == actor_user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .populate_existing()
        .first()
    )
    if membership is None:
        raise PermissionError("Active organization membership required")
    if source.scope == "org":
        return source
    if source.owner_user_id != actor_user_id and membership.role not in (
        Role.ADMIN.value,
        Role.DEVELOPER.value,
    ):
        raise LookupError("Template not found")
    if not {"manage_email_templates", "manage_org_templates"}.issubset(
        permission_service.get_effective_permissions(db, org_id, actor_user_id, membership.role)
    ):
        raise PermissionError("Manage organization templates permission required")
    base_name = (name or source.name).strip()
    if not base_name or len(base_name) > 100:
        raise ValueError("Template name must contain 1 to 100 characters")
    existing_names = {
        row[0]
        for row in db.query(EmailTemplate.name)
        .filter(EmailTemplate.organization_id == org_id, EmailTemplate.scope == "org")
        .all()
    }
    if name and base_name in existing_names:
        raise ValueError("An organization template with this name already exists")
    resolved_name = base_name
    suffix = 2
    while resolved_name in existing_names:
        tail = f" ({suffix})"
        resolved_name = base_name[: 100 - len(tail)] + tail
        suffix += 1
    proposer = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(User.id == source.owner_user_id, Membership.organization_id == org_id)
        .first()
    )
    from app.services import email_service

    published = email_service.create_template(
        db,
        org_id=org_id,
        user_id=actor_user_id,
        name=resolved_name,
        subject=source.subject,
        from_email=source.from_email,
        body=source.body,
        scope="org",
        category=source.category,
        commit=False,
    )
    published.proposed_by_user_id = proposer.id if proposer else None
    published.proposed_by_name = proposer.display_name if proposer else None
    if source.owner_user_id != actor_user_id:
        audit_service.log_event(
            db,
            org_id=org_id,
            event_type=AuditEventType.CONFIG_TEMPLATE_UPDATED,
            actor_user_id=actor_user_id,
            target_type="email_template",
            target_id=source.id,
            details={"operation": "private_template_access"},
        )
    audit_service.log_event(
        db,
        org_id=org_id,
        event_type=AuditEventType.CONFIG_TEMPLATE_UPDATED,
        actor_user_id=actor_user_id,
        target_type="email_template",
        target_id=published.id,
        details={"action": "published_to_organization"},
    )
    return published
