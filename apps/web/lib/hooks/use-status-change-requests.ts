/**
 * React Query hooks for status change request approval workflow.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api/status-change-requests';
import type { ListStatusChangeRequestsParams } from '../api/status-change-requests';

// Query keys
export const statusChangeRequestKeys = {
    all: ['status-change-requests'] as const,
    lists: () => [...statusChangeRequestKeys.all, 'list'] as const,
    list: (params: ListStatusChangeRequestsParams) => [...statusChangeRequestKeys.lists(), params] as const,
    details: () => [...statusChangeRequestKeys.all, 'detail'] as const,
    detail: (id: string) => [...statusChangeRequestKeys.details(), id] as const,
};

/**
 * Fetch paginated list of pending status change requests.
 */
export function useStatusChangeRequests(
    params: ListStatusChangeRequestsParams = {},
    enabled: boolean = true
) {
    return useQuery({
        queryKey: statusChangeRequestKeys.list(params),
        queryFn: () => api.listPendingRequests(params),
        enabled,
    });
}

/**
 * Fetch a single status change request by ID.
 */
export function useStatusChangeRequest(requestId: string) {
    return useQuery({
        queryKey: statusChangeRequestKeys.detail(requestId),
        queryFn: () => api.getRequest(requestId),
        enabled: !!requestId,
    });
}

/**
 * Approve a pending status change request.
 */
export function useApproveStatusChangeRequest() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (requestId: string) => api.approveRequest(requestId),
        onSuccess: () => {
            // Invalidate all status change request lists
            queryClient.invalidateQueries({ queryKey: statusChangeRequestKeys.lists() });
            // Also invalidate surrogates since the approval changes the surrogate
            queryClient.invalidateQueries({ queryKey: ['surrogates'] });
        },
    });
}

/**
 * Reject a pending status change request.
 */
export function useRejectStatusChangeRequest() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ requestId, reason }: { requestId: string; reason?: string }) =>
            api.rejectRequest(requestId, reason),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: statusChangeRequestKeys.lists() });
        },
    });
}

/**
 * Cancel a pending status change request (requester only).
 */
export function useCancelStatusChangeRequest() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (requestId: string) => api.cancelRequest(requestId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: statusChangeRequestKeys.lists() });
        },
    });
}
