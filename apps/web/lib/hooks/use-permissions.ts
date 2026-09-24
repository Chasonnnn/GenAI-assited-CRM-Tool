/**
 * React Query hooks for permissions API.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
    getAvailablePermissions,
    getMembers,
    getMember,
    updateMember,
    removeMember,
    getMyEffectivePermissions,
    getRoles,
    getRoleDetail,
    updateRolePermissions,
    bulkUpdateRoles,
    getIntakePoolGrants,
    createIntakePoolGrant,
    revokeIntakePoolGrant,
    getPolicyConfiguration,
    previewPolicy,
    activatePolicy,
    type PolicyChanges,
    type MemberUpdate,
    type IntakePoolGrantCreate,
} from "@/lib/api/permissions"

// Query Keys
const KEYS = {
    permissions: ["permissions"] as const,
    members: ["permissions", "members"] as const,
    member: (id: string) => ["permissions", "members", id] as const,
    effectivePermissions: ["permissions", "effective"] as const,
    effective: (userId: string) => ["permissions", "effective", userId] as const,
    roles: ["permissions", "roles"] as const,
    role: (role: string) => ["permissions", "roles", role] as const,
    intakePoolGrants: (granteeUserId?: string) =>
        ["permissions", "intake-pool-grants", granteeUserId ?? "all"] as const,
}

// Hooks

export function useAvailablePermissions() {
    return useQuery({
        queryKey: KEYS.permissions,
        queryFn: getAvailablePermissions,
        staleTime: 1000 * 60 * 10, // 10 min cache
    })
}

export function useMembers(includeInactive = false) {
    return useQuery({
        queryKey: [...KEYS.members, { includeInactive }],
        queryFn: () => getMembers(includeInactive),
    })
}

export function useMember(memberId: string | null) {
    return useQuery({
        queryKey: KEYS.member(memberId || ""),
        queryFn: () => getMember(memberId!),
        enabled: !!memberId,
    })
}

export function useUpdateMember() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ memberId, data }: { memberId: string; data: MemberUpdate }) =>
            updateMember(memberId, data),
        onSuccess: () => queryClient.invalidateQueries(),
    })
}

export function useRemoveMember() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (memberId: string) => removeMember(memberId),
        onSuccess: () => queryClient.invalidateQueries(),
    })
}

export function useEffectivePermissions(userId: string | null) {
    return useQuery({
        queryKey: KEYS.effective(userId || ""),
        queryFn: getMyEffectivePermissions,
        enabled: !!userId,
    })
}

export function useIntakePoolGrants(
    granteeUserId?: string | null,
    options: { enabled?: boolean } = {},
) {
    return useQuery({
        queryKey: KEYS.intakePoolGrants(granteeUserId || undefined),
        queryFn: () => getIntakePoolGrants(granteeUserId || undefined),
        enabled: granteeUserId !== null && (options.enabled ?? true),
    })
}

export function useCreateIntakePoolGrant() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (data: IntakePoolGrantCreate) => createIntakePoolGrant(data),
        onSuccess: () => queryClient.invalidateQueries(),
    })
}

export function useRevokeIntakePoolGrant() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: revokeIntakePoolGrant,
        onSuccess: () => queryClient.invalidateQueries(),
    })
}

export function useRoles(enabled = true) {
    return useQuery({
        queryKey: KEYS.roles,
        queryFn: getRoles,
        enabled,
    })
}

export function useRoleDetail(role: string | null) {
    return useQuery({
        queryKey: KEYS.role(role || ""),
        queryFn: () => getRoleDetail(role!),
        enabled: !!role,
    })
}

export function useUpdateRolePermissions() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ role, permissions, scopeRules }: { role: string; permissions: Record<string, boolean>; scopeRules?: Partial<Record<import("@/lib/api/record-scopes").RecordModule, import("@/lib/api/record-scopes").RecordScopeRule>> }) =>
            updateRolePermissions(role, permissions, scopeRules),
        onSuccess: () => queryClient.invalidateQueries(),
    })
}

export function useBulkUpdateRoles() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ memberIds, role, review }: { memberIds: string[]; role: string; review?: Pick<MemberUpdate, "access_reviewed" | "retain_additions" | "retain_collaborators"> }) =>
            bulkUpdateRoles(memberIds, role, review),
        onSuccess: () => queryClient.invalidateQueries(),
    })
}

export function usePolicyConfiguration(enabled = true) {
    return useQuery({ queryKey: ["permissions", "policy"], queryFn: getPolicyConfiguration, enabled })
}
export function usePreviewPolicy() {
    return useMutation({ mutationFn: (changes: PolicyChanges) => previewPolicy(changes) })
}
export function useActivatePolicy() {
    const client = useQueryClient()
    return useMutation({ mutationFn: activatePolicy, onSuccess: () => client.invalidateQueries() })
}
