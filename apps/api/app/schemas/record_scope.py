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


ScopeAssignment = Literal["all", "assigned", "none"]
ScopePhase = Literal["all", "pre_approval", "post_approval"]
ApprovalPhase = Literal["pre_approval", "post_approval"]
HandoffDecision = Literal["retain_verified_owner", "no_verified_owner"]
PoolDecision = Literal["remove", "replace_with_scope_addition"]


class RoleScopeSnapshot(BaseModel):
    role: str
    module: RecordModule
    assignment: ScopeAssignment
    phase: ScopePhase
    stage_ids: list[UUID]


class IndividualScopeSnapshot(BaseModel):
    id: UUID
    user_id: UUID
    module: RecordModule
    assignment: ScopeAssignment
    phase: ScopePhase
    stage_ids: list[UUID]


class MigrationCollaborator(BaseModel):
    id: UUID
    record_number: str | None
    user_id: UUID
    surrogate_id: UUID | None
    donor_id: UUID | None


class HandoffCandidateRead(BaseModel):
    kind: Literal["surrogate", "donor"]
    record_id: UUID
    record_number: str | None
    fingerprint: str
    phase_requires_review: bool
    owner_user_id: UUID | None
    resolved: bool


class LegacyPoolGrantRead(BaseModel):
    id: UUID
    source_user_id: UUID
    grantee_user_id: UUID
    current_record_ids: list[UUID]
    choices: list[PoolDecision]
    fingerprint: str


class MemberScopeDifference(BaseModel):
    membership_id: UUID
    user_id: UUID
    role: str
    module: RecordModule
    scope_only: bool
    current_count: int
    proposed_count: int
    gained_count: int
    lost_count: int
    gained_record_id_samples: list[UUID]
    lost_record_id_samples: list[UUID]


class MigrationReviewResolution(BaseModel):
    id: UUID
    record_id: UUID
    decision: HandoffDecision
    retained_user_id: UUID | None
    record_fingerprint: str
    reviewed_by_user_id: UUID
    evidence_reference: str | None
    resolved_phase: ApprovalPhase | None
    reviewed_stage_id: UUID | None


class ScopeMigrationReviewRead(BaseModel):
    ready: bool
    default_role_scopes: dict[str, dict[RecordModule, RecordScopeRule]]
    role_scopes: list[RoleScopeSnapshot]
    individual_scopes: list[IndividualScopeSnapshot]
    collaborators: list[MigrationCollaborator]
    handoff_candidates: list[HandoffCandidateRead]
    unresolved_handoffs: list[HandoffCandidateRead]
    missing_approval_gate_pipeline_ids: list[UUID]
    legacy_pool_grants: list[LegacyPoolGrantRead]
    member_record_scope_differences: list[MemberScopeDifference]
    record_state_digest: str
    resolutions: list[MigrationReviewResolution]


class HandoffMigrationReviewResult(BaseModel):
    record_id: UUID
    decision: HandoffDecision
    resolved: bool


class LegacyPoolResolutionResult(BaseModel):
    resolved: bool
