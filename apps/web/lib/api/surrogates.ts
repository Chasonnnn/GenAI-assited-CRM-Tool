/**
 * Surrogates API client - typed functions for surrogate management endpoints.
 */

import api from './index';
import { getCsrfHeaders } from '@/lib/csrf';
import type { JsonObject } from '../types/json';
import type {
    SurrogateListResponse,
    SurrogateRead,
    SurrogateSource,
    SurrogateStatusChangePayload,
    SurrogateStatusChangeResponse,
    SurrogateStatusHistory,
} from '../types/surrogate';
import type { TaskListItem } from './tasks';

export type {
    SurrogateStatusChangePayload,
    SurrogateStatusChangeResponse,
    SurrogateStatusHistory,
};

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
    attachment_ids?: string[];
}

export interface SurrogateSendEmailResponse {
    success: boolean;
    email_log_id?: string | null;
    message_id?: string | null;
    provider_used?: string | null;
    error?: string | null;
}

export type SurrogateTemplateVariables = Record<string, string>;

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
 * Get resolved template variables for surrogate email preview.
 */
export function getSurrogateTemplateVariables(surrogateId: string): Promise<SurrogateTemplateVariables> {
    return api.get<SurrogateTemplateVariables>(`/surrogates/${surrogateId}/template-variables`);
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

export interface SurrogateCaseDetailsExportView {
    surrogate: SurrogateRead;
    activities: SurrogateActivity[];
    tasks: TaskListItem[];
    show_medical: boolean;
    show_pregnancy: boolean;
}

export interface SurrogatePacketExportResult {
    includesApplication: boolean;
}

// =============================================================================
// Developer Tools: Mass Edit (Dev Role Only)
// =============================================================================

export interface SurrogateMassEditOptionsResponse {
    races: string[];
}

export function getSurrogateMassEditOptions(): Promise<SurrogateMassEditOptionsResponse> {
    return api.get<SurrogateMassEditOptionsResponse>('/surrogates/mass-edit/options');
}

export interface SurrogateMassEditStageFilters {
    stage_ids?: string[]; // Current stage filter
    source?: SurrogateSource;
    queue_id?: string;
    q?: string;
    created_from?: string; // YYYY-MM-DD
    created_to?: string; // YYYY-MM-DD
    states?: string[]; // ["CA", "TX"]
    races?: string[]; // Normalized keys or labels (server normalizes)
    is_priority?: boolean;

    // Checklist
    is_age_eligible?: boolean;
    is_citizen_or_pr?: boolean;
    has_child?: boolean;
    is_non_smoker?: boolean;
    has_surrogate_experience?: boolean;
    num_deliveries_min?: number;
    num_deliveries_max?: number;
    num_csections_min?: number;
    num_csections_max?: number;

    // Derived fields
    age_min?: number;
    age_max?: number;
    bmi_min?: number;
    bmi_max?: number;
}

export interface SurrogateMassEditStagePreviewRequest {
    filters: SurrogateMassEditStageFilters;
}

export interface SurrogateMassEditStagePreviewItem {
    id: string;
    surrogate_number: string;
    full_name: string;
    state: string | null;
    stage_id: string;
    status_label: string;
    created_at: string;
    age?: number | null;
}

export interface SurrogateMassEditStagePreviewResponse {
    total: number;
    over_limit: boolean;
    max_apply: number;
    items: SurrogateMassEditStagePreviewItem[];
}

export function previewSurrogateMassEditStage(
    data: SurrogateMassEditStagePreviewRequest,
    limit: number = 25
): Promise<SurrogateMassEditStagePreviewResponse> {
    const searchParams = new URLSearchParams();
    searchParams.set('limit', String(limit));
    return api.post<SurrogateMassEditStagePreviewResponse>(`/surrogates/mass-edit/stage/preview?${searchParams.toString()}`, data);
}

export interface SurrogateMassEditStageApplyRequest {
    filters: SurrogateMassEditStageFilters;
    stage_id: string;
    expected_total: number;
    trigger_workflows?: boolean;
    reason?: string;
}

export interface SurrogateMassEditStageApplyFailure {
    surrogate_id: string;
    reason: string;
}

export interface SurrogateMassEditStageApplyResponse {
    matched: number;
    applied: number;
    pending_approval: number;
    failed: SurrogateMassEditStageApplyFailure[];
}

export function applySurrogateMassEditStage(
    data: SurrogateMassEditStageApplyRequest
): Promise<SurrogateMassEditStageApplyResponse> {
    return api.post<SurrogateMassEditStageApplyResponse>('/surrogates/mass-edit/stage', data);
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

export async function exportSurrogatePacketPdf(
    surrogateId: string,
): Promise<SurrogatePacketExportResult> {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    const url = `${baseUrl}/surrogates/${surrogateId}/export`;

    const response = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers: { ...getCsrfHeaders() },
    });
    if (!response.ok) {
        throw new Error(`Export failed (${response.status})`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/pdf')) {
        const errorText = await response.text();
        throw new Error(errorText || 'Export failed (unexpected response)');
    }

    const buffer = await response.arrayBuffer();
    const headerBytes = new Uint8Array(buffer.slice(0, 4));
    const headerText = String.fromCharCode(...headerBytes);
    if (headerText !== '%PDF') {
        const errorText = new TextDecoder().decode(buffer);
        throw new Error(errorText || 'Export failed (invalid PDF)');
    }

    const includesApplication =
        (response.headers.get('x-includes-application') || '').toLowerCase() === 'true';
    const contentDisposition = response.headers.get('content-disposition') || '';
    const filenameMatch =
        contentDisposition.match(/filename\*=UTF-8''([^;]+)/i) ||
        contentDisposition.match(/filename="?([^";]+)"?/i);
    let downloadFilename = `surrogate_export_${surrogateId}.pdf`;
    if (filenameMatch?.[1]) {
        try {
            downloadFilename = decodeURIComponent(filenameMatch[1]);
        } catch {
            downloadFilename = filenameMatch[1];
        }
    }

    const blob = new Blob([buffer], { type: 'application/pdf' });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = downloadFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(objectUrl);

    return { includesApplication };
}

// =============================================================================
// Interview Outcome Tracking
// =============================================================================

export type InterviewOutcome = 'completed' | 'no_show' | 'rescheduled' | 'cancelled';

export interface InterviewOutcomeCreatePayload {
    outcome: InterviewOutcome;
    occurred_at?: string | null; // ISO datetime, defaults to now
    notes?: string | null;
    appointment_id?: string | null;
}

/**
 * Log an interview outcome for a surrogate.
 */
export function logInterviewOutcome(
    surrogateId: string,
    data: InterviewOutcomeCreatePayload
): Promise<SurrogateActivity> {
    return api.post<SurrogateActivity>(`/surrogates/${surrogateId}/interview-outcomes`, data);
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
