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
    detail: (surrogateId: string) => [...profileKeys.all, surrogateId] as const,
}

export function useProfile(surrogateId: string | null) {
    return useQuery({
        queryKey: profileKeys.detail(surrogateId || ''),
        queryFn: () => getProfile(surrogateId!),
        enabled: !!surrogateId,
        retry: false,
    })
}

export function useSyncProfile() {
    return useMutation({
        mutationFn: (surrogateId: string) => syncProfile(surrogateId),
        onSuccess: () => {
            // Don't invalidate - sync returns staged changes, not persisted
        },
    })
}

export function useSaveProfileOverrides() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            surrogateId,
            overrides,
            newBaseSubmissionId,
        }: {
            surrogateId: string
            overrides: JsonObject
            newBaseSubmissionId?: string | null
        }) => saveProfileOverrides(surrogateId, overrides, newBaseSubmissionId),
        onSuccess: (_, { surrogateId }) => {
            queryClient.invalidateQueries({ queryKey: profileKeys.detail(surrogateId) })
        },
    })
}

export function useToggleProfileHidden() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            surrogateId,
            fieldKey,
            hidden,
        }: {
            surrogateId: string
            fieldKey: string
            hidden: boolean
        }) => toggleProfileHiddenField(surrogateId, fieldKey, hidden),
        onSuccess: (_, { surrogateId }) => {
            queryClient.invalidateQueries({ queryKey: profileKeys.detail(surrogateId) })
        },
    })
}
