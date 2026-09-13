"""Policy-aware admission for creating tenant records."""

from typing import Literal

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db
from app.schemas.auth import UserSession
from app.services import permission_policy_service, permission_service

RecordModule = Literal["surrogates", "donors", "intended_parents"]


def check_record_creation(
    db: Session, session: UserSession, module: RecordModule, *, v2_only: bool = False
) -> None:
    enabled = permission_policy_service.is_enabled(db, session.org_id)
    if v2_only and not enabled:
        return
    permission = f"{'create' if enabled else 'edit'}_{module}"
    if not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, permission
    ):
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")


def require_record_creation(module: RecordModule, *, v2_only: bool = False):
    def dependency(
        session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)
    ) -> UserSession:
        check_record_creation(db, session, module, v2_only=v2_only)
        return session

    return dependency
