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
        mutationFn: ({ caseId, userId }: { caseId: string; userId: string | null }) =>
            casesApi.assignCase(caseId, userId),
        onSuccess: (updatedCase) => {
            queryClient.setQueryData(caseKeys.detail(updatedCase.id), updatedCase);
            queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
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
