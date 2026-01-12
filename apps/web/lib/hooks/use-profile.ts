/**
 * React Query hooks for profile card.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    getProfile,
    syncProfile,
    saveProfileOverrides,
    toggleProfileHiddenField,
} from '@/lib/api/profile'
import type { JsonObject } from '@/lib/types/json'

export const profileKeys = {
    all: ['profile'] as const,
    detail: (caseId: string) => [...profileKeys.all, caseId] as const,
}

export function useProfile(caseId: string | null) {
    return useQuery({
        queryKey: profileKeys.detail(caseId || ''),
        queryFn: () => getProfile(caseId!),
        enabled: !!caseId,
        retry: false,
    })
}

export function useSyncProfile() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (caseId: string) => syncProfile(caseId),
        onSuccess: (_, caseId) => {
            // Don't invalidate - sync returns staged changes, not persisted
        },
    })
}

export function useSaveProfileOverrides() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            caseId,
            overrides,
            newBaseSubmissionId,
        }: {
            caseId: string
            overrides: JsonObject
            newBaseSubmissionId?: string | null
        }) => saveProfileOverrides(caseId, overrides, newBaseSubmissionId),
        onSuccess: (_, { caseId }) => {
            queryClient.invalidateQueries({ queryKey: profileKeys.detail(caseId) })
        },
    })
}

export function useToggleProfileHidden() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            caseId,
            fieldKey,
            hidden,
        }: {
            caseId: string
            fieldKey: string
            hidden: boolean
        }) => toggleProfileHiddenField(caseId, fieldKey, hidden),
        onSuccess: (_, { caseId }) => {
            queryClient.invalidateQueries({ queryKey: profileKeys.detail(caseId) })
        },
    })
}
