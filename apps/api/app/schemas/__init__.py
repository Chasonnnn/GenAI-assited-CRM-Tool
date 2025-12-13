"""Pydantic schemas for API request/response models."""

from app.schemas.auth import MeResponse, TokenPayload, UserSession
from app.schemas.invite import InviteCreate, InviteRead
from app.schemas.org import OrgCreate, OrgRead
from app.schemas.user import UserRead, UserUpdate
from app.schemas.case import (
    CaseAssign,
    CaseCreate,
    CaseListItem,
    CaseListResponse,
    CaseRead,
    CaseStatusChange,
    CaseStatusHistoryRead,
    CaseUpdate,
)
from app.schemas.note import NoteCreate, NoteRead
from app.schemas.task import (
    TaskCreate,
    TaskListItem,
    TaskListResponse,
    TaskRead,
    TaskUpdate,
)

__all__ = [
    # Auth
    "TokenPayload",
    "UserSession", 
    "MeResponse",
    # User
    "UserRead",
    "UserUpdate",
    # Org
    "OrgCreate",
    "OrgRead",
    # Invite
    "InviteCreate",
    "InviteRead",
    # Case
    "CaseCreate",
    "CaseUpdate",
    "CaseRead",
    "CaseListItem",
    "CaseListResponse",
    "CaseStatusChange",
    "CaseAssign",
    "CaseStatusHistoryRead",
    # Note
    "NoteCreate",
    "NoteRead",
    # Task
    "TaskCreate",
    "TaskUpdate",
    "TaskRead",
    "TaskListItem",
    "TaskListResponse",
]
