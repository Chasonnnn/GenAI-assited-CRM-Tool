/**
 * API client for permissions endpoints.
 */

import api from '../api'

// Types
export interface PermissionInfo {
    key: string
    label: string
    description: string
    category: string
    developer_only: boolean
    assignable?: boolean
}

export interface Member {
    id: string
    user_id: string
    email: string
    display_name: string | null
    role: string
    is_active?: boolean
    last_login_at: string | null
    created_at: string
}

interface PermissionOverride {
    permission: string
    override_type: "grant" | "revoke"
    label: string
    category: string
}

export interface MemberDetail extends Member {
    effective_permissions: string[]
    overrides: PermissionOverride[]
    policy_version?: number
    capabilities?: Record<string, boolean>
    access_sources?: Record<string, string[]>
}

export interface MemberUpdate {
    role?: string
    add_overrides?: { permission: string; override_type: "grant" | "revoke" }[]
    remove_overrides?: string[]
    access_reviewed?: boolean
    retain_additions?: boolean
    retain_collaborators?: boolean
}

export interface RoleSummary {
    role: string
    label: string
    permission_count: number
    is_developer: boolean
    protected?: boolean
    can_edit?: boolean
    policy_version?: number
}

export interface RolePermission {
    key: string
    label: string
    description: string
    is_granted: boolean
    developer_only: boolean
    configurable?: boolean
}

export interface RoleDetail {
    role: string
    label: string
    permissions_by_category: Record<string, RolePermission[]>
    protected?: boolean
    can_edit?: boolean
    policy_version?: number
}

export interface EffectivePermissions {
    user_id: string
    role: string
    permissions: string[]
    overrides: PermissionOverride[]
    policy_version?: number
    capabilities?: Record<string, boolean>
    access_sources?: Record<string, string[]>
}

export interface IntakePoolGrant {
    id: string
    source_user_id: string
    source_user_name: string | null
    source_user_email: string
    grantee_user_id: string
    grantee_user_name: string | null
    grantee_user_email: string
    created_by_user_id: string | null
    created_at: string
    updated_at: string
}

export interface IntakePoolGrantCreate {
    source_user_id: string
    grantee_user_id: string
}

// API Functions

export async function getAvailablePermissions(): Promise<PermissionInfo[]> {
    return api.get<PermissionInfo[]>("/settings/permissions/available")
}

export async function getMembers(includeInactive = false): Promise<Member[]> {
    return api.get<Member[]>(`/settings/permissions/members${includeInactive ? "?include_inactive=true" : ""}`)
}

export async function getMember(memberId: string): Promise<MemberDetail> {
    return api.get<MemberDetail>(`/settings/permissions/members/${memberId}`)
}

export async function updateMember(memberId: string, data: MemberUpdate): Promise<MemberDetail> {
    return api.patch<MemberDetail>(`/settings/permissions/members/${memberId}`, data)
}

export async function removeMember(memberId: string): Promise<{ removed: boolean; user_id: string }> {
    return api.delete<{ removed: boolean; user_id: string }>(`/settings/permissions/members/${memberId}`)
}

export async function getEffectivePermissions(userId: string): Promise<EffectivePermissions> {
    return api.get<EffectivePermissions>(`/settings/permissions/effective/${userId}`)
}

export async function getMyEffectivePermissions(): Promise<EffectivePermissions> {
    return api.get<EffectivePermissions>("/settings/permissions/effective/me")
}

export async function getIntakePoolGrants(granteeUserId?: string): Promise<IntakePoolGrant[]> {
    const query = granteeUserId ? `?grantee_user_id=${encodeURIComponent(granteeUserId)}` : ""
    return api.get<IntakePoolGrant[]>(`/settings/permissions/intake-pool-grants${query}`)
}

export async function createIntakePoolGrant(data: IntakePoolGrantCreate): Promise<IntakePoolGrant> {
    return api.post<IntakePoolGrant>("/settings/permissions/intake-pool-grants", data)
}

export async function revokeIntakePoolGrant(grantId: string): Promise<{ removed: boolean; id: string }> {
    return api.delete<{ removed: boolean; id: string }>(`/settings/permissions/intake-pool-grants/${grantId}`)
}

export async function getRoles(): Promise<RoleSummary[]> {
    return api.get<RoleSummary[]>("/settings/permissions/roles")
}

export async function getRoleDetail(role: string): Promise<RoleDetail> {
    return api.get<RoleDetail>(`/settings/permissions/roles/${role}`)
}

export async function updateRolePermissions(
    role: string,
    permissions: Record<string, boolean>,
    scopeRules?: Partial<Record<import("./record-scopes").RecordModule, import("./record-scopes").RecordScopeRule>>,
): Promise<RoleDetail> {
    return api.patch<RoleDetail>(`/settings/permissions/roles/${role}`, { permissions, ...(scopeRules ? { scope_rules: scopeRules } : {}) })
}

export async function bulkUpdateRoles(
    memberIds: string[],
    role: string,
    review: Pick<MemberUpdate, "access_reviewed" | "retain_additions" | "retain_collaborators"> = {},
): Promise<{ success: number; failed: number }> {
    // Update members in parallel
    const results = await Promise.allSettled(
        memberIds.map(id => api.patch(`/settings/permissions/members/${id}`, { role, ...review }))
    )
    const success = results.filter(r => r.status === "fulfilled").length
    const failed = results.filter(r => r.status === "rejected").length
    return { success, failed }
}

export interface PolicyChanges {
    role_permissions?: Record<string, Record<string, boolean>>
    revoke_resolutions?: { override_id: string; action: "remove" | "deny_for_role" }[]
    execution_resolutions?: { item_type: "workflow" | "campaign"; id: string; action: "pause" }[]
}

export interface PolicyConfiguration {
    version: number
    configuration_revision: number
    status: "legacy" | "active"
    role_permissions: Record<string, Record<string, boolean>>
    protected_roles: string[]
}

export interface PolicyPreview {
    digest: string
    current_version: number
    target_version: number
    configuration_revision: number
    ready: boolean
    members: {
        membership_id: string
        user_id: string
        role: string
        current: string[]
        proposed: string[]
        gained: string[]
        lost: string[]
    }[]
    revokes: { override_id: string; user_id: string; role: string | null; permission: string; resolution: "remove" | "deny_for_role" | null; can_deny_for_role?: boolean }[]
    unresolved_revoke_ids: string[]
    role_permissions: Record<string, Record<string, boolean>>
    scope_review: import("./record-scopes").ScopeMigrationReview
    execution_review: { item_type: "workflow" | "campaign"; id: string; name?: string; unreviewed_execution_ids?: string[] }[]
    unresolved_execution_ids: string[]
}

export const getPolicyConfiguration = () => api.get<PolicyConfiguration>("/settings/permissions/policy")
export const previewPolicy = (changes: PolicyChanges) => api.post<PolicyPreview>("/settings/permissions/policy/preview", changes)
export const activatePolicy = (changes: PolicyChanges & { digest: string }) => api.post<PolicyConfiguration>("/settings/permissions/policy/activate", changes)
