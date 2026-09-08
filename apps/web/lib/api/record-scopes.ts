import api from "../api"

export type RecordModule = "surrogates" | "donors" | "intended_parents"
export type RecordKind = "surrogate" | "donor" | "intended_parent"
export interface RecordScopeRule {
    assignment: "all" | "assigned" | "none"
    phase: "all" | "pre_approval" | "post_approval"
    stage_ids: string[]
}
export interface ScopeAddition extends RecordScopeRule {
    id: string
    user_id: string
    module: RecordModule
    created_at: string
}
export interface RecordCollaborator {
    record_number?: string
    display_name?: string | null
    id: string
    user_id: string
    surrogate_id: string | null
    donor_id: string | null
    granted_by_user_id?: string | null
    created_at?: string
}
export interface HandoffCandidate {
    kind: "surrogate" | "donor"
    record_id: string
    fingerprint: string
    record_number?: string
    name?: string
    owner_user_id?: string | null
    phase_requires_review?: boolean
    resolved?: boolean
}
export interface LegacyPoolGrant {
    id: string
    source_user_id: string
    grantee_user_id: string
    current_record_ids: string[]
    fingerprint: string
}
export interface ScopeMigrationReview {
    ready: boolean
    collaborators: RecordCollaborator[]
    handoff_candidates: HandoffCandidate[]
    unresolved_handoffs: HandoffCandidate[]
    missing_approval_gate_pipeline_ids: string[]
    legacy_pool_grants: LegacyPoolGrant[]
}
export interface RecordAccessResult {
    allowed: boolean
    sources: string[]
    reason: string | null
}
export const getRoleScopes = (role: string) => api.get<Record<RecordModule, RecordScopeRule>>(`/record-scopes/roles/${role}`)
export const updateRoleScope = (role: string, module: RecordModule, rule: RecordScopeRule) => api.put<RecordScopeRule>(`/record-scopes/roles/${role}/${module}`, rule)
export const getScopeAdditions = (userId: string) => api.get<ScopeAddition[]>(`/record-scopes/members/${userId}/additions`)
export const addScopeAddition = (userId: string, rule: RecordScopeRule & { module: RecordModule }) => api.post<ScopeAddition>(`/record-scopes/members/${userId}/additions`, rule)
export const removeScopeAddition = (userId: string, id: string) => api.delete(`/record-scopes/members/${userId}/additions/${id}`)
export const getScopeMigrationReview = () => api.get<ScopeMigrationReview>("/record-scopes/migration-review")
export const checkRecordAccess = (request: { user_id: string; kind: RecordKind; record_id: string; personal_only: boolean }) => api.post<RecordAccessResult>("/record-scopes/check", request)
export const removeCollaborator = (kind: "surrogate" | "donor", recordId: string, userId: string) => api.delete(`/record-scopes/records/${kind}/${recordId}/collaborators/${userId}`)
export const addCollaborator = (kind: "surrogate" | "donor", recordId: string, userId: string) => api.post<RecordCollaborator>(`/record-scopes/records/${kind}/${recordId}/collaborators`, { user_id: userId })
export const reviewHandoff = (candidate: HandoffCandidate, review: {
    decision: "retain_verified_owner" | "no_verified_owner"
    intake_user_id?: string
    evidence_reference: string
    resolved_phase?: "pre_approval" | "post_approval"
}) => api.post(`/record-scopes/migration-review/records/${candidate.kind}/${candidate.record_id}`, { ...review, expected_fingerprint: candidate.fingerprint })
export const reviewPoolGrant = (grant: LegacyPoolGrant, decision: "remove" | "replace_with_scope_addition", replacement?: RecordScopeRule & { module: RecordModule }) => api.post(`/record-scopes/migration-review/pool-grants/${grant.id}`, { decision, replacement, expected_fingerprint: grant.fingerprint })

export const getCollaborators = (kind: "surrogate" | "donor", recordId: string) => api.get<RecordCollaborator[]>(`/record-scopes/records/${kind}/${recordId}/collaborators`)
export const getCollaboratorOptions = (kind: "surrogate" | "donor", recordId: string) => api.get<{user_id: string; display_name: string}[]>(`/record-scopes/records/${kind}/${recordId}/collaborator-options`)
