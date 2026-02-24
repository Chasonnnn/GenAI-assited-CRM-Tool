/**
 * API client for permissions endpoints.
 */

import api from "@/lib/api"

// Types
export interface PermissionInfo {
    key: string
    label: string
    description: string
    category: string
    developer_only: boolean
}

export interface Member {
    id: string
    user_id: string
    email: string
    display_name: string | null
    role: string
    last_login_at: string | null
    created_at: string
}

export interface PermissionOverride {
    permission: string
    override_type: "grant" | "revoke"
    label: string
    category: string
}

export interface MemberDetail extends Member {
    effective_permissions: string[]
    overrides: PermissionOverride[]
}

export interface MemberUpdate {
    role?: string
    add_overrides?: { permission: string; override_type: "grant" | "revoke" }[]
    remove_overrides?: string[]
}

export interface RoleSummary {
    role: string
    label: string
    permission_count: number
    is_developer: boolean
}

export interface RolePermission {
    key: string
    label: string
    description: string
    is_granted: boolean
    developer_only: boolean
}

export interface RoleDetail {
    role: string
    label: string
    permissions_by_category: Record<string, RolePermission[]>
}

export interface EffectivePermissions {
    user_id: string
    role: string
    permissions: string[]
    overrides: PermissionOverride[]
}

// API Functions

export async function getAvailablePermissions(): Promise<PermissionInfo[]> {
    return api.get<PermissionInfo[]>("/settings/permissions/available")
}

export async function getMembers(): Promise<Member[]> {
    return api.get<Member[]>("/settings/permissions/members")
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

export async function getRoles(): Promise<RoleSummary[]> {
    return api.get<RoleSummary[]>("/settings/permissions/roles")
}

export async function getRoleDetail(role: string): Promise<RoleDetail> {
    return api.get<RoleDetail>(`/settings/permissions/roles/${role}`)
}

export async function updateRolePermissions(
    role: string,
    permissions: Record<string, boolean>
): Promise<RoleDetail> {
    return api.patch<RoleDetail>(`/settings/permissions/roles/${role}`, { permissions })
}

export async function bulkUpdateRoles(
    memberIds: string[],
    role: string
): Promise<{ success: number; failed: number }> {
    // Update members in parallel
    const results = await Promise.allSettled(
        memberIds.map(id => api.patch(`/settings/permissions/members/${id}`, { role }))
    )
    const success = results.filter(r => r.status === "fulfilled").length
    const failed = results.filter(r => r.status === "rejected").length
    return { success, failed }
}
