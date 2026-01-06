/**
 * React Query hooks for session management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    getSessions,
    revokeSession,
    revokeAllSessions,
    uploadAvatar,
    deleteAvatar,
    Session,
} from '@/lib/api/settings'

// =============================================================================
// Query Keys
// =============================================================================

export const sessionKeys = {
    all: ['sessions'] as const,
    list: () => [...sessionKeys.all, 'list'] as const,
}

export const avatarKeys = {
    all: ['avatar'] as const,
}

// =============================================================================
// Session Hooks
// =============================================================================

export function useSessions() {
    return useQuery({
        queryKey: sessionKeys.list(),
        queryFn: getSessions,
    })
}

export function useRevokeSession() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (sessionId: string) => revokeSession(sessionId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: sessionKeys.list() })
        },
    })
}

export function useRevokeAllSessions() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: () => revokeAllSessions(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: sessionKeys.list() })
        },
    })
}

// =============================================================================
// Avatar Hooks
// =============================================================================

export function useUploadAvatar() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (file: File) => uploadAvatar(file),
        onSuccess: () => {
            // Invalidate user data to refresh avatar URL
            queryClient.invalidateQueries({ queryKey: ['user'] })
            queryClient.invalidateQueries({ queryKey: ['me'] })
        },
    })
}

export function useDeleteAvatar() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: () => deleteAvatar(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['user'] })
            queryClient.invalidateQueries({ queryKey: ['me'] })
        },
    })
}

// =============================================================================
// Types re-export for convenience
// =============================================================================

export type { Session }
