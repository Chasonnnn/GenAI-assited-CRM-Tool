/**
 * React Query hooks for Cases module.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as casesApi from '../api/cases';
import type { CaseListParams } from '../api/cases';

// Query keys
export const caseKeys = {
    all: ['cases'] as const,
    lists: () => [...caseKeys.all, 'list'] as const,
    list: (params: CaseListParams) => [...caseKeys.lists(), params] as const,
    stats: () => [...caseKeys.all, 'stats'] as const,
    details: () => [...caseKeys.all, 'detail'] as const,
    detail: (id: string) => [...caseKeys.details(), id] as const,
    history: (id: string) => [...caseKeys.detail(id), 'history'] as const,
};

/**
 * Fetch case statistics for dashboard.
 */
export function useCaseStats() {
    return useQuery({
        queryKey: caseKeys.stats(),
        queryFn: casesApi.getCaseStats,
        staleTime: 30 * 1000, // 30 seconds
    });
}

/**
 * Fetch paginated cases list.
 */
export function useCases(params: CaseListParams = {}) {
    return useQuery({
        queryKey: caseKeys.list(params),
        queryFn: () => casesApi.getCases(params),
    });
}

/**
 * Fetch single case by ID.
 */
export function useCase(caseId: string) {
    return useQuery({
        queryKey: caseKeys.detail(caseId),
        queryFn: () => casesApi.getCase(caseId),
        enabled: !!caseId,
    });
}

/**
 * Fetch case status history.
 */
export function useCaseHistory(caseId: string) {
    return useQuery({
        queryKey: caseKeys.history(caseId),
        queryFn: () => casesApi.getCaseHistory(caseId),
        enabled: !!caseId,
    });
}

/**
 * Create a new case.
 */
export function useCreateCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: casesApi.createCase,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
        },
    });
}

/**
 * Update case fields.
 */
export function useUpdateCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ caseId, data }: { caseId: string; data: casesApi.CaseUpdatePayload }) =>
            casesApi.updateCase(caseId, data),
        onSuccess: (updatedCase) => {
            queryClient.setQueryData(caseKeys.detail(updatedCase.id), updatedCase);
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
        },
    });
}

/**
 * Change case status.
 */
export function useChangeStatus() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ caseId, data }: { caseId: string; data: casesApi.CaseStatusChangePayload }) =>
            casesApi.changeCaseStatus(caseId, data),
        onSuccess: (updatedCase) => {
            queryClient.setQueryData(caseKeys.detail(updatedCase.id), updatedCase);
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: caseKeys.history(updatedCase.id) });
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
        },
    });
}

/**
 * Assign case to user.
 */
export function useAssignCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            caseId,
            owner_type,
            owner_id,
        }: {
            caseId: string;
            owner_type: 'user' | 'queue';
            owner_id: string;
        }) => casesApi.assignCase(caseId, { owner_type, owner_id }),
        onSuccess: (updatedCase) => {
            queryClient.setQueryData(caseKeys.detail(updatedCase.id), updatedCase);
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
        },
    });
}

/**
 * Send an email to a case contact using a template.
 */
export function useSendCaseEmail() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({ caseId, data }: { caseId: string; data: casesApi.CaseSendEmailPayload }) => {
            const result = await casesApi.sendCaseEmail(caseId, data);
            if (!result.success) {
                throw new Error(result.error || "Failed to send email");
            }
            return result;
        },
        onSuccess: (_, { caseId }) => {
            queryClient.invalidateQueries({ queryKey: [...caseKeys.detail(caseId), 'activity'] });
        },
    });
}

/**
 * Archive a case.
 */
export function useArchiveCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: casesApi.archiveCase,
        onSuccess: (updatedCase) => {
            queryClient.setQueryData(caseKeys.detail(updatedCase.id), updatedCase);
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
        },
    });
}

/**
 * Restore an archived case.
 */
export function useRestoreCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: casesApi.restoreCase,
        onSuccess: (updatedCase) => {
            queryClient.setQueryData(caseKeys.detail(updatedCase.id), updatedCase);
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
        },
    });
}

// =============================================================================
// Handoff Workflow Hooks (Case Manager+ only)
// =============================================================================

export const handoffKeys = {
    queue: () => ['cases', 'handoff-queue'] as const,
    queuePage: (page: number) => [...handoffKeys.queue(), { page }] as const,
};

/**
 * Fetch cases in pending_handoff status (case_manager+ only).
 * Pass enabled: false to skip the query for non-case-manager roles.
 */
export function useHandoffQueue(
    params: casesApi.HandoffQueueParams = {},
    options: { enabled?: boolean } = {}
) {
    return useQuery({
        queryKey: handoffKeys.queuePage(params.page || 1),
        queryFn: () => casesApi.getHandoffQueue(params),
        enabled: options.enabled !== false,
    });
}

/**
 * Accept a pending_handoff case → transitions to pending_match.
 */
export function useAcceptHandoff() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: casesApi.acceptHandoff,
        onSuccess: (updatedCase) => {
            queryClient.setQueryData(caseKeys.detail(updatedCase.id), updatedCase);
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: handoffKeys.queue() });
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
            queryClient.invalidateQueries({ queryKey: caseKeys.history(updatedCase.id) });
        },
    });
}

/**
 * Deny a pending_handoff case → reverts to under_review.
 */
export function useDenyHandoff() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ caseId, reason }: { caseId: string; reason?: string }) =>
            casesApi.denyHandoff(caseId, reason),
        onSuccess: (updatedCase) => {
            queryClient.setQueryData(caseKeys.detail(updatedCase.id), updatedCase);
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: handoffKeys.queue() });
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
            queryClient.invalidateQueries({ queryKey: caseKeys.history(updatedCase.id) });
        },
    });
}

/**
 * Fetch list of org members who can be assigned cases.
 */
export function useAssignees() {
    return useQuery({
        queryKey: [...caseKeys.all, 'assignees'],
        queryFn: casesApi.getAssignees,
        staleTime: 60 * 1000, // 1 minute
    });
}

/**
 * Bulk assign multiple cases to a user.
 */
export function useBulkAssign() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: casesApi.bulkAssignCases,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
        },
    });
}

/**
 * Bulk archive multiple cases.
 */
export function useBulkArchive() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: casesApi.bulkArchiveCases,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
            queryClient.invalidateQueries({ queryKey: caseKeys.stats() });
        },
    });
}

/**
 * Fetch case activity log (paginated).
 */
export function useCaseActivity(caseId: string, page: number = 1, perPage: number = 20) {
    return useQuery({
        queryKey: [...caseKeys.detail(caseId), 'activity', { page, perPage }],
        queryFn: () => casesApi.getCaseActivity(caseId, page, perPage),
        enabled: !!caseId,
    });
}
