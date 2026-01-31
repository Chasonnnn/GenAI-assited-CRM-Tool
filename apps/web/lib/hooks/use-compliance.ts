/**
 * React Query hooks for compliance features
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
    listRetentionPolicies,
    upsertRetentionPolicy,
    listLegalHolds,
    createLegalHold,
    releaseLegalHold,
    previewPurge,
    executePurge,
    RetentionPolicyUpsert,
    LegalHoldCreate,
    LegalHoldListParams,
} from '@/lib/api/compliance'

export const complianceKeys = {
    all: ['compliance'] as const,
    policies: () => [...complianceKeys.all, 'policies'] as const,
    holds: () => [...complianceKeys.all, 'holds'] as const,
    holdsList: (params: LegalHoldListParams) => [...complianceKeys.holds(), params] as const,
    purgePreview: () => [...complianceKeys.all, 'purge-preview'] as const,
}

export function useRetentionPolicies() {
    return useQuery({
        queryKey: complianceKeys.policies(),
        queryFn: listRetentionPolicies,
    })
}

export function useUpsertRetentionPolicy() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: RetentionPolicyUpsert) => upsertRetentionPolicy(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: complianceKeys.policies() })
        },
    })
}

export function useLegalHolds(params: LegalHoldListParams = {}) {
    return useQuery({
        queryKey: complianceKeys.holdsList(params),
        queryFn: () => listLegalHolds(params),
    })
}

export function useCreateLegalHold() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (data: LegalHoldCreate) => createLegalHold(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: complianceKeys.holds() })
        },
    })
}

export function useReleaseLegalHold() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (id: string) => releaseLegalHold(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: complianceKeys.holds() })
        },
    })
}

export function usePurgePreview() {
    return useQuery({
        queryKey: complianceKeys.purgePreview(),
        queryFn: previewPurge,
        enabled: false,
    })
}

export function useExecutePurge() {
    return useMutation({
        mutationFn: () => executePurge(),
    })
}
