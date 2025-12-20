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
    const res = await api.get<PermissionInfo[]>("/settings/permissions/available")
    return res.data
}

export async function getMembers(): Promise<Member[]> {
    const res = await api.get<Member[]>("/settings/permissions/members")
    return res.data
}

export async function getMember(memberId: string): Promise<MemberDetail> {
    const res = await api.get<MemberDetail>(`/settings/permissions/members/${memberId}`)
    return res.data
}

export async function updateMember(memberId: string, data: MemberUpdate): Promise<MemberDetail> {
    const res = await api.patch<MemberDetail>(`/settings/permissions/members/${memberId}`, data)
    return res.data
}

export async function removeMember(memberId: string): Promise<{ removed: boolean; user_id: string }> {
    const res = await api.delete<{ removed: boolean; user_id: string }>(`/settings/permissions/members/${memberId}`)
    return res.data
}

export async function getEffectivePermissions(userId: string): Promise<EffectivePermissions> {
    const res = await api.get<EffectivePermissions>(`/settings/permissions/effective/${userId}`)
    return res.data
}

export async function getRoles(): Promise<RoleSummary[]> {
    const res = await api.get<RoleSummary[]>("/settings/permissions/roles")
    return res.data
}

export async function getRoleDetail(role: string): Promise<RoleDetail> {
    const res = await api.get<RoleDetail>(`/settings/permissions/roles/${role}`)
    return res.data
}

export async function updateRolePermissions(
    role: string,
    permissions: Record<string, boolean>
): Promise<RoleDetail> {
    const res = await api.patch<RoleDetail>(`/settings/permissions/roles/${role}`, { permissions })
    return res.data
}
