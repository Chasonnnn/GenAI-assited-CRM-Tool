"""Pydantic schemas for API request/response models."""

from app.schemas.auth import MeResponse, TokenPayload, UserSession
from app.schemas.invite import InviteCreate, InviteRead
from app.schemas.note import NoteCreate, NoteRead
from app.schemas.org import OrgCreate, OrgRead
from app.schemas.surrogate import (
    SurrogateAssign,
    SurrogateCreate,
    SurrogateListItem,
    SurrogateListResponse,
    SurrogateRead,
    SurrogateStatusChange,
    SurrogateStatusHistoryRead,
    SurrogateUpdate,
)
from app.schemas.task import (
    TaskCreate,
    TaskListItem,
    TaskListResponse,
    TaskRead,
    TaskUpdate,
)
from app.schemas.user import UserRead, UserUpdate

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
    # Surrogate
    "SurrogateCreate",
    "SurrogateUpdate",
    "SurrogateRead",
    "SurrogateListItem",
    "SurrogateListResponse",
    "SurrogateStatusChange",
    "SurrogateAssign",
    "SurrogateStatusHistoryRead",
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
