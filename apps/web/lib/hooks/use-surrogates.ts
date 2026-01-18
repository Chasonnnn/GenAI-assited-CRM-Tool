/**
 * React Query hooks for Surrogates module.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as surrogatesApi from '../api/surrogates';
import type { SurrogateListParams } from '../api/surrogates';

// Query keys
export const surrogateKeys = {
    all: ['surrogates'] as const,
    lists: () => [...surrogateKeys.all, 'list'] as const,
    list: (params: SurrogateListParams) => [...surrogateKeys.lists(), params] as const,
    stats: () => [...surrogateKeys.all, 'stats'] as const,
    details: () => [...surrogateKeys.all, 'detail'] as const,
    detail: (id: string) => [...surrogateKeys.details(), id] as const,
    history: (id: string) => [...surrogateKeys.detail(id), 'history'] as const,
};

/**
 * Fetch surrogate statistics for dashboard.
 * Auto-refreshes every 60 seconds for real-time updates.
 */
export function useSurrogateStats(params: surrogatesApi.SurrogateStatsParams = {}) {
    return useQuery({
        queryKey: [...surrogateKeys.stats(), params] as const,
        queryFn: () => surrogatesApi.getSurrogateStats(params),
        staleTime: 30 * 1000, // 30 seconds
        refetchInterval: (query) => (query.state.status === 'error' ? false : 60 * 1000),
    });
}

/**
 * Fetch paginated surrogates list.
 */
export function useSurrogates(params: SurrogateListParams = {}) {
    return useQuery({
        queryKey: surrogateKeys.list(params),
        queryFn: () => surrogatesApi.getSurrogates(params),
    });
}

/**
 * Fetch single surrogate by ID.
 */
export function useSurrogate(surrogateId: string) {
    return useQuery({
        queryKey: surrogateKeys.detail(surrogateId),
        queryFn: () => surrogatesApi.getSurrogate(surrogateId),
        enabled: !!surrogateId,
    });
}

/**
 * Fetch surrogate status history.
 */
export function useSurrogateHistory(surrogateId: string) {
    return useQuery({
        queryKey: surrogateKeys.history(surrogateId),
        queryFn: () => surrogatesApi.getSurrogateHistory(surrogateId),
        enabled: !!surrogateId,
    });
}

/**
 * Create a new surrogate.
 */
export function useCreateSurrogate() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: surrogatesApi.createSurrogate,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
            queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
        },
    });
}

/**
 * Update surrogate fields.
 */
export function useUpdateSurrogate() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ surrogateId, data }: { surrogateId: string; data: surrogatesApi.SurrogateUpdatePayload }) =>
            surrogatesApi.updateSurrogate(surrogateId, data),
        onSuccess: (updatedSurrogate) => {
            queryClient.setQueryData(surrogateKeys.detail(updatedSurrogate.id), updatedSurrogate);
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
        },
    });
}

/**
 * Change surrogate status/stage.
 * Returns { status: 'applied' | 'pending_approval', surrogate?, request_id? }
 */
export function useChangeSurrogateStatus() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ surrogateId, data }: { surrogateId: string; data: surrogatesApi.SurrogateStatusChangePayload }) =>
            surrogatesApi.changeSurrogateStatus(surrogateId, data),
        onSuccess: (response, { surrogateId }) => {
            // If change was applied immediately, update the cache
            if (response.status === 'applied' && response.surrogate) {
                queryClient.setQueryData(surrogateKeys.detail(response.surrogate.id), response.surrogate);
            }
            // Invalidate related queries
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
            queryClient.invalidateQueries({ queryKey: surrogateKeys.history(surrogateId) });
            queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
            queryClient.invalidateQueries({ queryKey: surrogateKeys.detail(surrogateId) });
        },
    });
}

/**
 * Assign surrogate to user.
 */
export function useAssignSurrogate() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            surrogateId,
            owner_type,
            owner_id,
        }: {
            surrogateId: string;
            owner_type: 'user' | 'queue';
            owner_id: string;
        }) => surrogatesApi.assignSurrogate(surrogateId, { owner_type, owner_id }),
        onSuccess: (updatedSurrogate) => {
            queryClient.setQueryData(surrogateKeys.detail(updatedSurrogate.id), updatedSurrogate);
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
        },
    });
}

/**
 * Send an email to a surrogate contact using a template.
 */
export function useSendSurrogateEmail() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({ surrogateId, data }: { surrogateId: string; data: surrogatesApi.SurrogateSendEmailPayload }) => {
            const result = await surrogatesApi.sendSurrogateEmail(surrogateId, data);
            if (!result.success) {
                throw new Error(result.error || "Failed to send email");
            }
            return result;
        },
        onSuccess: (_, { surrogateId }) => {
            queryClient.invalidateQueries({ queryKey: [...surrogateKeys.detail(surrogateId), 'activity'] });
        },
    });
}

/**
 * Archive a surrogate.
 */
export function useArchiveSurrogate() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: surrogatesApi.archiveSurrogate,
        onSuccess: (updatedSurrogate) => {
            queryClient.setQueryData(surrogateKeys.detail(updatedSurrogate.id), updatedSurrogate);
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
            queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
        },
    });
}

/**
 * Restore an archived surrogate.
 */
export function useRestoreSurrogate() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: surrogatesApi.restoreSurrogate,
        onSuccess: (updatedSurrogate) => {
            queryClient.setQueryData(surrogateKeys.detail(updatedSurrogate.id), updatedSurrogate);
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
            queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
        },
    });
}

/**
 * Fetch list of org members who can be assigned surrogates.
 */
export function useAssignees() {
    return useQuery({
        queryKey: [...surrogateKeys.all, 'assignees'],
        queryFn: surrogatesApi.getAssignees,
        staleTime: 60 * 1000, // 1 minute
    });
}

/**
 * Bulk assign multiple surrogates to a user.
 */
export function useBulkAssign() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: surrogatesApi.bulkAssignSurrogates,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
            queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
        },
    });
}

/**
 * Bulk archive multiple surrogates.
 */
export function useBulkArchive() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: surrogatesApi.bulkArchiveSurrogates,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
            queryClient.invalidateQueries({ queryKey: surrogateKeys.stats() });
        },
    });
}

/**
 * Fetch surrogate activity log (paginated).
 */
export function useSurrogateActivity(surrogateId: string, page: number = 1, perPage: number = 20) {
    return useQuery({
        queryKey: [...surrogateKeys.detail(surrogateId), 'activity', { page, perPage }],
        queryFn: () => surrogatesApi.getSurrogateActivity(surrogateId, page, perPage),
        enabled: !!surrogateId,
    });
}

// =============================================================================
// Contact Attempts Tracking Hooks
// =============================================================================

export const contactAttemptKeys = {
    all: (surrogateId: string) => [...surrogateKeys.detail(surrogateId), 'contact-attempts'] as const,
};

/**
 * Fetch contact attempts summary for a surrogate.
 */
export function useContactAttempts(surrogateId: string) {
    return useQuery({
        queryKey: contactAttemptKeys.all(surrogateId),
        queryFn: () => surrogatesApi.getContactAttempts(surrogateId),
        enabled: !!surrogateId,
    });
}

/**
 * Log a new contact attempt for a surrogate.
 */
export function useCreateContactAttempt() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ surrogateId, data }: { surrogateId: string; data: surrogatesApi.ContactAttemptCreatePayload }) =>
            surrogatesApi.createContactAttempt(surrogateId, data),
        onSuccess: (_, { surrogateId }) => {
            // Invalidate contact attempts summary
            queryClient.invalidateQueries({ queryKey: contactAttemptKeys.all(surrogateId) });
            // Invalidate surrogate detail (contact_status may have changed)
            queryClient.invalidateQueries({ queryKey: surrogateKeys.detail(surrogateId) });
            // Invalidate activity log (new activity entry)
            queryClient.invalidateQueries({ queryKey: [...surrogateKeys.detail(surrogateId), 'activity'] });
            // Invalidate surrogate lists (status may have changed)
            queryClient.invalidateQueries({ queryKey: surrogateKeys.lists() });
        },
    });
}
