/**
 * React Query hooks for Cases API.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { CaseListResponse, CaseRead } from '@/lib/types/case';

// Query keys
export const caseKeys = {
    all: ['cases'] as const,
    lists: () => [...caseKeys.all, 'list'] as const,
    list: (filters: Record<string, unknown>) => [...caseKeys.lists(), filters] as const,
    details: () => [...caseKeys.all, 'detail'] as const,
    detail: (id: string) => [...caseKeys.details(), id] as const,
};

// List cases
interface ListCasesParams {
    page?: number;
    per_page?: number;
    status?: string;
    source?: string;
    assigned_to?: string;
    q?: string;
    include_archived?: boolean;
}

export function useCases(params: ListCasesParams = {}) {
    const queryParams = new URLSearchParams();

    if (params.page) queryParams.set('page', String(params.page));
    if (params.per_page) queryParams.set('per_page', String(params.per_page));
    if (params.status) queryParams.set('status', params.status);
    if (params.source) queryParams.set('source', params.source);
    if (params.assigned_to) queryParams.set('assigned_to', params.assigned_to);
    if (params.q) queryParams.set('q', params.q);
    if (params.include_archived) queryParams.set('include_archived', 'true');

    const queryString = queryParams.toString();
    const path = queryString ? `/cases?${queryString}` : '/cases';

    return useQuery({
        queryKey: caseKeys.list(params as Record<string, unknown>),
        queryFn: () => api.get<CaseListResponse>(path),
    });
}

// Get single case
export function useCase(id: string) {
    return useQuery({
        queryKey: caseKeys.detail(id),
        queryFn: () => api.get<CaseRead>(`/cases/${id}`),
        enabled: !!id,
    });
}

// Archive case
export function useArchiveCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => api.post(`/cases/${id}/archive`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: caseKeys.all });
        },
    });
}

// Restore case
export function useRestoreCase() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => api.post(`/cases/${id}/restore`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: caseKeys.all });
        },
    });
}
