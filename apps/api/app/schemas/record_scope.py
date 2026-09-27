"""Record scope configuration and effective-access results."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RecordModule = Literal["surrogates", "donors", "intended_parents"]
RecordKind = Literal["surrogate", "donor", "intended_parent"]


class RecordScopeRule(BaseModel):
    assignment: Literal["all", "assigned", "none"]
    phase: Literal["all", "pre_approval", "post_approval"] = "all"
    stage_ids: list[UUID] = Field(default_factory=list, max_length=100)


class RecordScopeAdditionCreate(RecordScopeRule):
    assignment: Literal["all", "assigned"]
    module: RecordModule


class RecordScopeAdditionRead(RecordScopeAdditionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    created_at: datetime


class CollaboratorCreate(BaseModel):
    user_id: UUID


class CollaboratorOption(BaseModel):
    user_id: UUID
    display_name: str


class CollaboratorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    surrogate_id: UUID | None
    donor_id: UUID | None
    granted_by_user_id: UUID | None
    display_name: str | None = None
    created_at: datetime


class CheckRecordAccessRequest(BaseModel):
    user_id: UUID
    kind: RecordKind
    record_id: UUID
    personal_only: bool = False


class RecordAccessExplanation(BaseModel):
    allowed: bool
    sources: list[str] = Field(default_factory=list)
    reason: str | None = None


class HandoffMigrationReviewRequest(BaseModel):
    decision: Literal["retain_verified_owner", "no_verified_owner"]
    intake_user_id: UUID | None = None
    evidence_reference: str | None = Field(default=None, max_length=500)
    expected_fingerprint: str
    resolved_phase: Literal["pre_approval", "post_approval"] | None = None


class LegacyPoolResolutionRequest(BaseModel):
    expected_fingerprint: str
    decision: Literal["remove", "replace_with_scope_addition"]
    replacement: RecordScopeAdditionCreate | None = None
