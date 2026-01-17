/**
 * API client for status change request approval workflow.
 */

import api from './index';

// Types
export interface StatusChangeRequest {
    id: string;
    organization_id: string;
    entity_type: 'surrogate' | 'intended_parent' | 'match';
    entity_id: string;
    target_stage_id: string | null;
    target_status: string | null;
    effective_at: string; // ISO datetime
    reason: string;
    requested_by_user_id: string | null;
    requested_at: string; // ISO datetime
    status: 'pending' | 'approved' | 'rejected' | 'cancelled';
    approved_by_user_id: string | null;
    approved_at: string | null;
    rejected_by_user_id: string | null;
    rejected_at: string | null;
    cancelled_by_user_id: string | null;
    cancelled_at: string | null;
}

export interface StatusChangeRequestDetail {
    request: StatusChangeRequest;
    entity_name: string | null;
    entity_number: string | null;
    requester_name: string | null;
    target_stage_label: string | null;
    current_stage_label: string | null;
}

export interface StatusChangeRequestListResponse {
    items: StatusChangeRequestDetail[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export interface ListStatusChangeRequestsParams {
    entity_type?: 'surrogate' | 'intended_parent' | 'match';
    page?: number;
    per_page?: number;
}

/**
 * List pending status change requests (admin only).
 */
export function listPendingRequests(params: ListStatusChangeRequestsParams = {}): Promise<StatusChangeRequestListResponse> {
    const searchParams = new URLSearchParams();
    if (params.entity_type) searchParams.set('entity_type', params.entity_type);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));

    const query = searchParams.toString();
    return api.get<StatusChangeRequestListResponse>(`/status-change-requests${query ? `?${query}` : ''}`);
}

/**
 * Get a single status change request by ID.
 */
export function getRequest(requestId: string): Promise<StatusChangeRequestDetail> {
    return api.get<StatusChangeRequestDetail>(`/status-change-requests/${requestId}`);
}

/**
 * Approve a pending status change request (admin only).
 */
export function approveRequest(requestId: string): Promise<StatusChangeRequest> {
    return api.post<StatusChangeRequest>(`/status-change-requests/${requestId}/approve`);
}

/**
 * Reject a pending status change request (admin only).
 */
export function rejectRequest(requestId: string, reason?: string): Promise<StatusChangeRequest> {
    return api.post<StatusChangeRequest>(`/status-change-requests/${requestId}/reject`, reason ? { reason } : undefined);
}

/**
 * Cancel a pending status change request (requester only).
 */
export function cancelRequest(requestId: string): Promise<StatusChangeRequest> {
    return api.post<StatusChangeRequest>(`/status-change-requests/${requestId}/cancel`);
}
