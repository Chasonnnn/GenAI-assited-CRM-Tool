"""Permission policy configuration and reviewed activation contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RevokeResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    override_id: UUID
    action: Literal["remove", "deny_for_role"]


class ExecutionResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: Literal["workflow", "campaign"]
    id: UUID
    action: Literal["pause"]


class PermissionPolicyChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_permissions: dict[str, dict[str, bool]] = Field(default_factory=dict)
    revoke_resolutions: list[RevokeResolution] = Field(default_factory=list)
    execution_resolutions: list[ExecutionResolution] = Field(default_factory=list)


class PermissionPolicyActivate(PermissionPolicyChanges):
    digest: str = Field(min_length=64, max_length=64, pattern="^[a-f0-9]+$")


class PermissionPolicyConfiguration(BaseModel):
    version: int
    configuration_revision: int
    status: Literal["legacy", "active"]
    role_permissions: dict[str, dict[str, bool]]
    protected_roles: list[str]


class PermissionMemberDifference(BaseModel):
    membership_id: UUID
    user_id: UUID
    role: str
    current: list[str]
    proposed: list[str]
    gained: list[str]
    lost: list[str]


class LegacyRevoke(BaseModel):
    can_deny_for_role: bool = False
    override_id: UUID
    user_id: UUID
    role: str | None
    permission: str
    resolution: Literal["remove", "deny_for_role"] | None


class PermissionPolicyPreview(BaseModel):
    digest: str
    current_version: int
    target_version: int = 2
    configuration_revision: int
    ready: bool
    members: list[PermissionMemberDifference]
    revokes: list[LegacyRevoke]
    unresolved_revoke_ids: list[UUID]
    role_permissions: dict[str, dict[str, bool]]
    scope_review: dict = Field(default_factory=dict)
    execution_review: list[dict] = Field(default_factory=list)
    unresolved_execution_ids: list[str] = Field(default_factory=list)
