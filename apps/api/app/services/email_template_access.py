"""Shared authorization for editing organization and personal email templates.

Callers must load templates and drafts within the authenticated organization.
HTTP error status and disclosure remain the caller's responsibility.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.policies import POLICIES
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import permission_service


def capabilities(template, session, permissions: set[str]) -> dict[str, bool]:
    personal_authority = can_edit_personal_template(
        owner_user_id=template.owner_user_id, user_id=session.user_id, role=session.role
    )
    author = "manage_email_templates" in permissions
    edit = author and (
        "manage_org_templates" in permissions if template.scope == "org" else personal_authority
    )
    return {
        "can_edit": edit and not template.is_system_template,
        "can_send_test": edit and "send_email" in permissions and not template.is_system_template,
        "can_publish_to_org": template.scope == "personal"
        and personal_authority
        and author
        and "manage_org_templates" in permissions,
        "can_copy": template.scope == "org" and author and not template.is_system_template,
    }


def require_send_permission(db: Session, session: UserSession) -> None:
    from app.services import permission_policy_service

    if permission_policy_service.is_enabled(
        db, session.org_id
    ) and not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, "send_email"
    ):
        raise HTTPException(status_code=403, detail="Send email permission required")


def audit_private_read(db, session, template, *, target_type="email_template") -> bool:
    from app.db.enums import AuditEventType
    from app.services import audit_service, permission_policy_service

    if (
        template.scope != "personal"
        or template.owner_user_id == session.user_id
        or not permission_policy_service.is_enabled(db, session.org_id)
    ):
        return False
    audit_service.log_event(
        db,
        org_id=session.org_id,
        event_type=AuditEventType.CONFIG_TEMPLATE_UPDATED,
        actor_user_id=session.user_id,
        target_type=target_type,
        target_id=template.id,
        details={"operation": "private_template_access"},
    )
    return True


def can_edit_personal_template(*, owner_user_id: UUID | None, user_id: UUID, role: Role) -> bool:
    return owner_user_id == user_id or role in (Role.ADMIN, Role.DEVELOPER)


def has_manage_permission(db: Session, session: UserSession) -> bool:
    from app.services import permission_policy_service

    if permission_policy_service.is_enabled(db, session.org_id):
        return all(
            permission_service.check_permission(
                db, session.org_id, session.user_id, session.role.value, key
            )
            for key in ("manage_email_templates", "manage_org_templates")
        )
    manage_permission = POLICIES["email_templates"].actions["manage"]
    permission_key = (
        manage_permission.value if hasattr(manage_permission, "value") else str(manage_permission)
    )
    return permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, permission_key
    )


def can_edit_template(
    db: Session,
    session: UserSession,
    *,
    scope: str,
    owner_user_id: UUID | None,
) -> bool:
    if scope == "org":
        return has_manage_permission(db, session)
    from app.services import permission_policy_service

    if permission_policy_service.is_enabled(
        db, session.org_id
    ) and not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, "manage_email_templates"
    ):
        return False
    return can_edit_personal_template(
        owner_user_id=owner_user_id, user_id=session.user_id, role=session.role
    )
