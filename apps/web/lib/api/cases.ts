/**
 * Cases API client - typed functions for case management endpoints.
 */

import api from './index';
import type {
    CaseListItem,
    CaseListResponse,
    CaseRead,
    CaseStatus,
    CaseSource,
} from '../types/case';

// Query params for listing cases
export interface CaseListParams {
    page?: number;
    per_page?: number;
    status?: CaseStatus;
    source?: CaseSource;
    assigned_to?: string;
    q?: string;
    include_archived?: boolean;
}

// Stats response from /cases/stats
export interface CaseStats {
    total: number;
    by_status: Record<string, number>;
    this_week: number;
    this_month: number;
    pending_tasks: number;
}

// Status history entry
export interface CaseStatusHistory {
    id: string;
    from_status: string;
    to_status: string;
    changed_by_user_id: string | null;
    changed_by_name: string | null;
    reason: string | null;
    changed_at: string;
}

// Create case payload
export interface CaseCreatePayload {
    full_name: string;
    email: string;
    phone?: string;
    state?: string;
    date_of_birth?: string;
    race?: string;
    height_ft?: number;
    weight_lb?: number;
    is_age_eligible?: boolean;
    is_citizen_or_pr?: boolean;
    has_child?: boolean;
    is_non_smoker?: boolean;
    has_surrogate_experience?: boolean;
    num_deliveries?: number;
    num_csections?: number;
    source?: CaseSource;
}

// Update case payload (all optional)
export type CaseUpdatePayload = Partial<CaseCreatePayload>;

// Status change payload
export interface CaseStatusChangePayload {
    status: CaseStatus;
    reason?: string;
}

// Assign case payload
export interface CaseAssignPayload {
    user_id: string | null;
}

/**
 * Get case statistics for dashboard.
 */
export function getCaseStats(): Promise<CaseStats> {
    return api.get<CaseStats>('/cases/stats');
}

/**
 * List cases with filters and pagination.
 */
export function getCases(params: CaseListParams = {}): Promise<CaseListResponse> {
    const searchParams = new URLSearchParams();

    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));
    if (params.status) searchParams.set('status', params.status);
    if (params.source) searchParams.set('source', params.source);
    if (params.assigned_to) searchParams.set('assigned_to', params.assigned_to);
    if (params.q) searchParams.set('q', params.q);
    if (params.include_archived) searchParams.set('include_archived', 'true');

    const query = searchParams.toString();
    return api.get<CaseListResponse>(`/cases${query ? `?${query}` : ''}`);
}

/**
 * Get single case by ID.
 */
export function getCase(caseId: string): Promise<CaseRead> {
    return api.get<CaseRead>(`/cases/${caseId}`);
}

/**
 * Create a new case.
 */
export function createCase(data: CaseCreatePayload): Promise<CaseRead> {
    return api.post<CaseRead>('/cases', data);
}

/**
 * Update case fields.
 */
export function updateCase(caseId: string, data: CaseUpdatePayload): Promise<CaseRead> {
    return api.patch<CaseRead>(`/cases/${caseId}`, data);
}

/**
 * Change case status.
 */
export function changeCaseStatus(caseId: string, data: CaseStatusChangePayload): Promise<CaseRead> {
    return api.patch<CaseRead>(`/cases/${caseId}/status`, data);
}

/**
 * Assign case to a user (or unassign with null).
 */
export function assignCase(caseId: string, userId: string | null): Promise<CaseRead> {
    return api.patch<CaseRead>(`/cases/${caseId}/assign`, { user_id: userId });
}

/**
 * Archive (soft-delete) a case.
 */
export function archiveCase(caseId: string): Promise<CaseRead> {
    return api.post<CaseRead>(`/cases/${caseId}/archive`);
}

/**
 * Restore an archived case.
 */
export function restoreCase(caseId: string): Promise<CaseRead> {
    return api.post<CaseRead>(`/cases/${caseId}/restore`);
}

/**
 * Permanently delete a case (must be archived first).
 */
export function deleteCase(caseId: string): Promise<void> {
    return api.delete(`/cases/${caseId}`);
}

/**
 * Get status change history for a case.
 */
export function getCaseHistory(caseId: string): Promise<CaseStatusHistory[]> {
    return api.get<CaseStatusHistory[]>(`/cases/${caseId}/history`);
}

// =============================================================================
// Handoff Workflow (Case Manager+ only)
// =============================================================================

export interface HandoffQueueParams {
    page?: number;
    per_page?: number;
}

/**
 * Get cases in pending_handoff status (case_manager+ only).
 */
export function getHandoffQueue(params: HandoffQueueParams = {}): Promise<CaseListResponse> {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));

    const query = searchParams.toString();
    return api.get<CaseListResponse>(`/cases/handoff-queue${query ? `?${query}` : ''}`);
}

/**
 * Accept a pending_handoff case → transitions to pending_match.
 */
export function acceptHandoff(caseId: string): Promise<CaseRead> {
    return api.post<CaseRead>(`/cases/${caseId}/accept`);
}

/**
 * Deny a pending_handoff case → reverts to under_review.
 */
export function denyHandoff(caseId: string, reason?: string): Promise<CaseRead> {
    return api.post<CaseRead>(`/cases/${caseId}/deny`, { reason });
}
