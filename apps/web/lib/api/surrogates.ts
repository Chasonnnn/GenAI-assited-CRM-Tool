/**
 * Surrogates API client - typed functions for surrogate management endpoints.
 */

import api from './index';
import type { JsonObject } from '../types/json';
import type {
    SurrogateListResponse,
    SurrogateRead,
    SurrogateSource,
} from '../types/surrogate';

// Query params for listing surrogates
export interface SurrogateListParams {
    page?: number;
    per_page?: number;
    cursor?: string;
    include_total?: boolean;
    stage_id?: string;
    source?: SurrogateSource;
    owner_id?: string;
    q?: string;
    include_archived?: boolean;
    queue_id?: string;  // Filter by queue (when owner_type='queue')
    owner_type?: 'user' | 'queue';  // Filter by owner type
    created_from?: string;  // ISO date string
    created_to?: string;    // ISO date string
    sort_by?: string;       // Column to sort by
    sort_order?: 'asc' | 'desc';  // Sort direction
}

// Stats response from /surrogates/stats with period comparisons
export interface SurrogateStats {
    total: number;
    by_status: Record<string, number>;
    this_week: number;
    last_week: number;
    week_change_pct: number | null;
    new_leads_24h: number;
    new_leads_prev_24h: number;
    new_leads_change_pct: number | null;
    pending_tasks: number;
}

export interface SurrogateStatsParams {
    pipeline_id?: string;
    owner_id?: string;
}

// Status history entry
export interface SurrogateStatusHistory {
    id: string;
    from_stage_id: string | null;
    to_stage_id: string | null;
    from_label_snapshot: string | null;
    to_label_snapshot: string | null;
    changed_by_user_id: string | null;
    changed_by_name: string | null;
    reason: string | null;
    changed_at: string;
    effective_at?: string | null;
    recorded_at?: string | null;
}

// Create surrogate payload
export interface SurrogateCreatePayload {
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
    source?: SurrogateSource;
    is_priority?: boolean;
    assign_to_user?: boolean;
}

// Update surrogate payload (partial; mirrors backend SurrogateUpdate schema)
// - Omitted fields are not changed
// - `null` clears the value for nullable fields (phone/state/demographics/eligibility)
export interface SurrogateUpdatePayload {
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

    // Insurance info
    insurance_company?: string | null;
    insurance_plan_name?: string | null;
    insurance_phone?: string | null;
    insurance_policy_number?: string | null;
    insurance_member_id?: string | null;
    insurance_group_number?: string | null;
    insurance_subscriber_name?: string | null;
    insurance_subscriber_dob?: string | null;

    // IVF Clinic
    clinic_name?: string | null;
    clinic_address_line1?: string | null;
    clinic_address_line2?: string | null;
    clinic_city?: string | null;
    clinic_state?: string | null;
    clinic_postal?: string | null;
    clinic_phone?: string | null;
    clinic_email?: string | null;

    // Monitoring Clinic
    monitoring_clinic_name?: string | null;
    monitoring_clinic_address_line1?: string | null;
    monitoring_clinic_address_line2?: string | null;
    monitoring_clinic_city?: string | null;
    monitoring_clinic_state?: string | null;
    monitoring_clinic_postal?: string | null;
    monitoring_clinic_phone?: string | null;
    monitoring_clinic_email?: string | null;

    // OB Provider
    ob_provider_name?: string | null;
    ob_clinic_name?: string | null;
    ob_address_line1?: string | null;
    ob_address_line2?: string | null;
    ob_city?: string | null;
    ob_state?: string | null;
    ob_postal?: string | null;
    ob_phone?: string | null;
    ob_email?: string | null;

    // Delivery Hospital
    delivery_hospital_name?: string | null;
    delivery_hospital_address_line1?: string | null;
    delivery_hospital_address_line2?: string | null;
    delivery_hospital_city?: string | null;
    delivery_hospital_state?: string | null;
    delivery_hospital_postal?: string | null;
    delivery_hospital_phone?: string | null;
    delivery_hospital_email?: string | null;

    // Pregnancy tracking
    pregnancy_start_date?: string | null;
    pregnancy_due_date?: string | null;
    actual_delivery_date?: string | null;
    delivery_baby_gender?: string | null;
    delivery_baby_weight?: string | null;
}

// Status change payload
export interface SurrogateStatusChangePayload {
    stage_id: string;
    reason?: string;
    effective_at?: string; // ISO datetime, optional (defaults to now)
    delivery_baby_gender?: string | null;
    delivery_baby_weight?: string | null;
}

// Status change response
export interface SurrogateStatusChangeResponse {
    status: 'applied' | 'pending_approval';
    surrogate?: SurrogateRead | null;
    request_id?: string | null;
    message?: string | null;
}

// Assign surrogate payload
export interface SurrogateAssignPayload {
    owner_type: 'user' | 'queue';
    owner_id: string;
}

export interface SurrogateSendEmailPayload {
    template_id: string;
    subject?: string;
    body?: string;
    provider?: 'auto' | 'gmail' | 'resend';
    idempotency_key?: string;
}

export interface SurrogateSendEmailResponse {
    success: boolean;
    email_log_id?: string | null;
    message_id?: string | null;
    provider_used?: string | null;
    error?: string | null;
}

/**
 * Get surrogate statistics for dashboard.
 */
export function getSurrogateStats(params: SurrogateStatsParams = {}): Promise<SurrogateStats> {
    const searchParams = new URLSearchParams();
    if (params.pipeline_id) searchParams.set('pipeline_id', params.pipeline_id);
    if (params.owner_id) searchParams.set('owner_id', params.owner_id);
    const query = searchParams.toString();
    return api.get<SurrogateStats>(`/surrogates/stats${query ? `?${query}` : ''}`);
}

export function getSurrogates(params: SurrogateListParams = {}): Promise<SurrogateListResponse> {
    const searchParams = new URLSearchParams();

    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));
    if (params.cursor) searchParams.set('cursor', params.cursor);
    if (params.include_total !== undefined) {
        searchParams.set('include_total', params.include_total ? 'true' : 'false');
    }
    if (params.stage_id) searchParams.set('stage_id', params.stage_id);
    if (params.source) searchParams.set('source', params.source);
    if (params.owner_id) searchParams.set('owner_id', params.owner_id);
    if (params.q) searchParams.set('q', params.q);
    if (params.include_archived) searchParams.set('include_archived', 'true');
    if (params.queue_id) searchParams.set('queue_id', params.queue_id);
    if (params.owner_type) searchParams.set('owner_type', params.owner_type);
    if (params.created_from) searchParams.set('created_from', params.created_from);
    if (params.created_to) searchParams.set('created_to', params.created_to);
    if (params.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params.sort_order) searchParams.set('sort_order', params.sort_order);

    const query = searchParams.toString();
    return api.get<SurrogateListResponse>(`/surrogates${query ? `?${query}` : ''}`);
}

export interface UnassignedQueueParams {
    page?: number;
    per_page?: number;
}

/**
 * List surrogates in the system Unassigned queue.
 */
export function getUnassignedQueue(params: UnassignedQueueParams = {}): Promise<SurrogateListResponse> {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', String(params.page));
    if (params.per_page) searchParams.set('per_page', String(params.per_page));
    const query = searchParams.toString();
    return api.get<SurrogateListResponse>(`/surrogates/unassigned-queue${query ? `?${query}` : ''}`);
}

/**
 * Claim a surrogate from a queue.
 *
 * - Intake specialists: only from Unassigned queue.
 * - Case managers/admin/developer: from any queue (subject to membership rules).
 */
export function claimSurrogate(surrogateId: string): Promise<{ message: string; surrogate_id: string }> {
    return api.post<{ message: string; surrogate_id: string }>(`/surrogates/${surrogateId}/claim`);
}

/**
 * Get single surrogate by ID.
 */
export function getSurrogate(surrogateId: string): Promise<SurrogateRead> {
    return api.get<SurrogateRead>(`/surrogates/${surrogateId}`);
}

/**
 * Create a new surrogate.
 */
export function createSurrogate(data: SurrogateCreatePayload): Promise<SurrogateRead> {
    return api.post<SurrogateRead>('/surrogates', data);
}

/**
 * Update surrogate fields.
 */
export function updateSurrogate(surrogateId: string, data: SurrogateUpdatePayload): Promise<SurrogateRead> {
    return api.patch<SurrogateRead>(`/surrogates/${surrogateId}`, data);
}

/**
 * Change surrogate status/stage.
 * Returns status: 'applied' if change was applied immediately,
 * or 'pending_approval' if the change requires admin approval (regression).
 */
export function changeSurrogateStatus(surrogateId: string, data: SurrogateStatusChangePayload): Promise<SurrogateStatusChangeResponse> {
    return api.patch<SurrogateStatusChangeResponse>(`/surrogates/${surrogateId}/status`, data);
}

/**
 * Assign surrogate to a user (or unassign with null).
 */
export function assignSurrogate(surrogateId: string, data: SurrogateAssignPayload): Promise<SurrogateRead> {
    return api.patch<SurrogateRead>(`/surrogates/${surrogateId}/assign`, data);
}

/**
 * Send an email to a surrogate contact using a template.
 */
export function sendSurrogateEmail(surrogateId: string, data: SurrogateSendEmailPayload): Promise<SurrogateSendEmailResponse> {
    return api.post<SurrogateSendEmailResponse>(`/surrogates/${surrogateId}/send-email`, data);
}

/**
 * Archive (soft-delete) a surrogate.
 */
export function archiveSurrogate(surrogateId: string): Promise<SurrogateRead> {
    return api.post<SurrogateRead>(`/surrogates/${surrogateId}/archive`);
}

/**
 * Restore an archived surrogate.
 */
export function restoreSurrogate(surrogateId: string): Promise<SurrogateRead> {
    return api.post<SurrogateRead>(`/surrogates/${surrogateId}/restore`);
}

/**
 * Permanently delete a surrogate (must be archived first).
 */
export function deleteSurrogate(surrogateId: string): Promise<void> {
    return api.delete(`/surrogates/${surrogateId}`);
}

/**
 * Get status change history for a surrogate.
 */
export function getSurrogateHistory(surrogateId: string): Promise<SurrogateStatusHistory[]> {
    return api.get<SurrogateStatusHistory[]>(`/surrogates/${surrogateId}/history`);
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
 * Get list of org members who can be assigned surrogates.
 */
export function getAssignees(): Promise<Assignee[]> {
    return api.get<Assignee[]>('/surrogates/assignees');
}

export interface BulkAssignPayload {
    surrogate_ids: string[];
    owner_type: 'user' | 'queue';
    owner_id: string;
}

export interface BulkAssignResult {
    assigned: number;
    failed: { surrogate_id: string; reason: string }[];
}

/**
 * Bulk assign multiple surrogates to a user.
 */
export function bulkAssignSurrogates(data: BulkAssignPayload): Promise<BulkAssignResult> {
    return api.post<BulkAssignResult>('/surrogates/bulk-assign', data);
}

/**
 * Bulk archive multiple surrogates.
 */
export function bulkArchiveSurrogates(surrogateIds: string[]): Promise<{ archived: number; failed: string[] }> {
    // Archive surrogates one by one - backend doesn't have bulk archive yet
    return Promise.all(surrogateIds.map(id => archiveSurrogate(id).catch(() => null)))
        .then(results => ({
            archived: results.filter(r => r !== null).length,
            failed: surrogateIds.filter((_, i) => results[i] === null),
        }));
}

// =============================================================================
// Activity Log
// =============================================================================

export interface SurrogateActivity {
    id: string;
    activity_type: string;
    actor_user_id: string | null;
    actor_name: string | null;
    details: JsonObject | null;
    created_at: string;
}

export interface SurrogateActivityResponse {
    items: SurrogateActivity[];
    total: number;
    page: number;
    pages: number;
}

/**
 * Get comprehensive activity log for a surrogate (paginated).
 */
export function getSurrogateActivity(
    surrogateId: string,
    page: number = 1,
    perPage: number = 20
): Promise<SurrogateActivityResponse> {
    const searchParams = new URLSearchParams();
    searchParams.set('page', String(page));
    searchParams.set('per_page', String(perPage));
    return api.get<SurrogateActivityResponse>(`/surrogates/${surrogateId}/activity?${searchParams.toString()}`);
}

// =============================================================================
// Contact Attempts Tracking
// =============================================================================

export type ContactMethod = 'phone' | 'email' | 'sms';
export type ContactOutcome = 'reached' | 'no_answer' | 'voicemail' | 'wrong_number' | 'email_bounced';

export interface ContactAttemptCreatePayload {
    contact_methods: ContactMethod[];
    outcome: ContactOutcome;
    notes?: string | null;
    attempted_at?: string | null; // ISO datetime, defaults to now
}

export interface ContactAttemptResponse {
    id: string;
    surrogate_id: string;
    attempted_by_user_id: string | null;
    attempted_by_name: string | null;
    contact_methods: string[];
    outcome: string;
    notes: string | null;
    attempted_at: string;
    created_at: string;
    is_backdated: boolean;
    surrogate_owner_id_at_attempt: string;
}

export interface ContactAttemptsSummary {
    total_attempts: number;
    current_assignment_attempts: number;
    distinct_days_current_assignment: number;
    successful_attempts: number;
    last_attempt_at: string | null;
    days_since_last_attempt: number | null;
    attempts: ContactAttemptResponse[];
}

/**
 * Log a contact attempt for a surrogate.
 */
export function createContactAttempt(
    surrogateId: string,
    data: ContactAttemptCreatePayload
): Promise<ContactAttemptResponse> {
    return api.post<ContactAttemptResponse>(`/surrogates/${surrogateId}/contact-attempts`, data);
}

/**
 * Get contact attempts summary for a surrogate.
 */
export function getContactAttempts(surrogateId: string): Promise<ContactAttemptsSummary> {
    return api.get<ContactAttemptsSummary>(`/surrogates/${surrogateId}/contact-attempts`);
}
