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
    type MemberUpdate,
    type IntakePoolGrantCreate,
} from "@/lib/api/permissions"

// Query Keys
const KEYS = {
    permissions: ["permissions"] as const,
    members: ["permissions", "members"] as const,
    member: (id: string) => ["permissions", "members", id] as const,
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

export function useMembers() {
    return useQuery({
        queryKey: KEYS.members,
        queryFn: getMembers,
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
        onSuccess: (_, { memberId }) => {
            void queryClient.invalidateQueries({ queryKey: KEYS.member(memberId) })
            void queryClient.invalidateQueries({ queryKey: KEYS.members })
        },
    })
}

export function useRemoveMember() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (memberId: string) => removeMember(memberId),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: KEYS.members })
        },
    })
}

export function useEffectivePermissions(userId: string | null) {
    return useQuery({
        queryKey: KEYS.effective("me"),
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
        onSuccess: (grant) => {
            void queryClient.invalidateQueries({ queryKey: KEYS.intakePoolGrants() })
            void queryClient.invalidateQueries({ queryKey: KEYS.intakePoolGrants(grant.grantee_user_id) })
            void queryClient.invalidateQueries({ queryKey: ["surrogates", "accessible-owners"] })
        },
    })
}

export function useRevokeIntakePoolGrant() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: revokeIntakePoolGrant,
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ["permissions", "intake-pool-grants"] })
            void queryClient.invalidateQueries({ queryKey: ["surrogates", "accessible-owners"] })
        },
    })
}

export function useRoles() {
    return useQuery({
        queryKey: KEYS.roles,
        queryFn: getRoles,
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
        mutationFn: ({ role, permissions }: { role: string; permissions: Record<string, boolean> }) =>
            updateRolePermissions(role, permissions),
        onSuccess: (_, { role }) => {
            void queryClient.invalidateQueries({ queryKey: KEYS.role(role) })
            void queryClient.invalidateQueries({ queryKey: KEYS.roles })
        },
    })
}

export function useBulkUpdateRoles() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ memberIds, role }: { memberIds: string[]; role: string }) =>
            bulkUpdateRoles(memberIds, role),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: KEYS.members })
        },
    })
}
