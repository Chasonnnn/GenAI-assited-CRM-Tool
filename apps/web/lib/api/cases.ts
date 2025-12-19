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
    owner_id?: string;
    q?: string;
    include_archived?: boolean;
    queue_id?: string;  // Filter by queue (when owner_type='queue')
    owner_type?: 'user' | 'queue';  // Filter by owner type
    created_from?: string;  // ISO date string
    created_to?: string;    // ISO date string
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
    is_priority?: boolean;
}

// Update case payload (partial; mirrors backend CaseUpdate schema)
// - Omitted fields are not changed
// - `null` clears the value for nullable fields (phone/state/demographics/eligibility)
export interface CaseUpdatePayload {
    full_name?: string;
    email?: string;
    phone?: string | null;
    state?: string | null;
    date_of_birth?: string | null;
    race?: string | null;
    height_ft?: number | null;
    weight_lb?: number | null;
    is_age_eligible?: boolean | null;
    is_citizen_or_pr?: boolean | null;
    has_child?: boolean | null;
    is_non_smoker?: boolean | null;
    has_surrogate_experience?: boolean | null;
    num_deliveries?: number | null;
    num_csections?: number | null;
    is_priority?: boolean;
}

// Status change payload
export interface CaseStatusChangePayload {
    status: CaseStatus;
    reason?: string;
}

// Assign case payload
export interface CaseAssignPayload {
    owner_type: 'user' | 'queue';
    owner_id: string;
}

/**
 * Get case statistics for dashboard.
 */
export function getCaseStats(): Promise<CaseStats> {
    return api.get<CaseStats>('/cases/stats');
}

export function getCases(params: CaseListParams = {}): Promise<CaseListResponse> {
    const searchParams = new URLSearchParams();

    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));
    if (params.status) searchParams.set('status', params.status);
    if (params.source) searchParams.set('source', params.source);
    if (params.owner_id) searchParams.set('owner_id', params.owner_id);
    if (params.q) searchParams.set('q', params.q);
    if (params.include_archived) searchParams.set('include_archived', 'true');
    if (params.queue_id) searchParams.set('queue_id', params.queue_id);
    if (params.owner_type) searchParams.set('owner_type', params.owner_type);
    if (params.created_from) searchParams.set('created_from', params.created_from);
    if (params.created_to) searchParams.set('created_to', params.created_to);

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
export function assignCase(caseId: string, data: CaseAssignPayload): Promise<CaseRead> {
    return api.patch<CaseRead>(`/cases/${caseId}/assign`, data);
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

// =============================================================================
// Bulk Operations
// =============================================================================

export interface Assignee {
    id: string;
    name: string;
    role: string;
}

/**
 * Get list of org members who can be assigned cases.
 */
export function getAssignees(): Promise<Assignee[]> {
    return api.get<Assignee[]>('/cases/assignees');
}

export interface BulkAssignPayload {
    case_ids: string[];
    owner_type: 'user' | 'queue';
    owner_id: string;
}

export interface BulkAssignResult {
    assigned: number;
    failed: { case_id: string; reason: string }[];
}

/**
 * Bulk assign multiple cases to a user.
 */
export function bulkAssignCases(data: BulkAssignPayload): Promise<BulkAssignResult> {
    return api.post<BulkAssignResult>('/cases/bulk-assign', data);
}

/**
 * Bulk archive multiple cases.
 */
export function bulkArchiveCases(caseIds: string[]): Promise<{ archived: number; failed: string[] }> {
    // Archive cases one by one - backend doesn't have bulk archive yet
    return Promise.all(caseIds.map(id => archiveCase(id).catch(() => null)))
        .then(results => ({
            archived: results.filter(r => r !== null).length,
            failed: caseIds.filter((_, i) => results[i] === null),
        }));
}

// =============================================================================
// Activity Log
// =============================================================================

export interface CaseActivity {
    id: string;
    activity_type: string;
    actor_user_id: string | null;
    actor_name: string | null;
    details: Record<string, unknown> | null;
    created_at: string;
}

export interface CaseActivityResponse {
    items: CaseActivity[];
    total: number;
    page: number;
    pages: number;
}

/**
 * Get comprehensive activity log for a case (paginated).
 */
export function getCaseActivity(
    caseId: string,
    page: number = 1,
    perPage: number = 20
): Promise<CaseActivityResponse> {
    const searchParams = new URLSearchParams();
    searchParams.set('page', String(page));
    searchParams.set('per_page', String(perPage));
    return api.get<CaseActivityResponse>(`/cases/${caseId}/activity?${searchParams.toString()}`);
}
