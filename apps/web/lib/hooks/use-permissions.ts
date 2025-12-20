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
    getEffectivePermissions,
    getRoles,
    getRoleDetail,
    updateRolePermissions,
    type MemberUpdate,
} from "@/lib/api/permissions"

// Query Keys
const KEYS = {
    permissions: ["permissions"] as const,
    members: ["permissions", "members"] as const,
    member: (id: string) => ["permissions", "members", id] as const,
    effective: (userId: string) => ["permissions", "effective", userId] as const,
    roles: ["permissions", "roles"] as const,
    role: (role: string) => ["permissions", "roles", role] as const,
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
            queryClient.invalidateQueries({ queryKey: KEYS.member(memberId) })
            queryClient.invalidateQueries({ queryKey: KEYS.members })
        },
    })
}

export function useRemoveMember() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (memberId: string) => removeMember(memberId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: KEYS.members })
        },
    })
}

export function useEffectivePermissions(userId: string | null) {
    return useQuery({
        queryKey: KEYS.effective(userId || ""),
        queryFn: () => getEffectivePermissions(userId!),
        enabled: !!userId,
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
            queryClient.invalidateQueries({ queryKey: KEYS.role(role) })
            queryClient.invalidateQueries({ queryKey: KEYS.roles })
        },
    })
}
