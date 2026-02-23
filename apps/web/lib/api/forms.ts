/**
 * Forms API client
 */

import api from './index'
import { getCsrfHeaders } from '@/lib/csrf'
import type { JsonObject } from '../types/json'

export type FormStatus = 'draft' | 'published' | 'archived'
export type FormPurpose = 'surrogate_application' | 'event_intake' | 'other'
export type FormSubmissionStatus = 'pending_review' | 'approved' | 'rejected'
export type FormLinkMode = 'dedicated' | 'shared'
export type SharedSubmissionOutcome = 'linked' | 'ambiguous_review' | 'lead_created'

export type FieldType =
    | 'text'
    | 'textarea'
    | 'email'
    | 'phone'
    | 'number'
    | 'date'
    | 'select'
    | 'multiselect'
    | 'radio'
    | 'checkbox'
    | 'file'
    | 'address'
    | 'repeatable_table'

export interface FormFieldOption {
    label: string
    value: string
}

export interface FormFieldValidation {
    min_length?: number | null
    max_length?: number | null
    min_value?: number | null
    max_value?: number | null
    pattern?: string | null
}

export type ConditionOperator =
    | 'equals'
    | 'not_equals'
    | 'contains'
    | 'not_contains'
    | 'is_empty'
    | 'is_not_empty'

export interface FormFieldCondition {
    field_key: string
    operator: ConditionOperator
    value?: unknown
}

export type TableColumnType = 'text' | 'number' | 'date' | 'select'

export interface FormFieldColumn {
    key: string
    label: string
    type: TableColumnType
    required?: boolean
    options?: FormFieldOption[] | null
    validation?: FormFieldValidation | null
}

export interface FormField {
    key: string
    label: string
    type: FieldType
    required?: boolean
    options?: FormFieldOption[] | null
    validation?: FormFieldValidation | null
    help_text?: string | null
    show_if?: FormFieldCondition | null
    columns?: FormFieldColumn[] | null
    min_rows?: number | null
    max_rows?: number | null
}

export interface FormPage {
    title?: string | null
    fields: FormField[]
}

export interface FormSchema {
    pages: FormPage[]
    public_title?: string | null
    logo_url?: string | null
    privacy_notice?: string | null
}

export interface FormSummary {
    id: string
    name: string
    status: FormStatus
    purpose?: FormPurpose
    is_default_surrogate_application?: boolean
    created_at: string
    updated_at: string
}

export interface FormRead extends FormSummary {
    description?: string | null
    form_schema?: FormSchema | null
    published_schema?: FormSchema | null
    max_file_size_bytes: number
    max_file_count: number
    allowed_mime_types?: string[] | null
    default_application_email_template_id?: string | null
}

export interface FormCreatePayload {
    name: string
    description?: string | null
    purpose?: FormPurpose
    form_schema?: FormSchema | null
    max_file_size_bytes?: number | null
    max_file_count?: number | null
    allowed_mime_types?: string[] | null
    default_application_email_template_id?: string | null
}

export interface FormUpdatePayload {
    name?: string | null
    description?: string | null
    purpose?: FormPurpose | null
    form_schema?: FormSchema | null
    max_file_size_bytes?: number | null
    max_file_count?: number | null
    allowed_mime_types?: string[] | null
    default_application_email_template_id?: string | null
}

export interface FormPublishResponse {
    id: string
    status: FormStatus
    published_at: string
}

export interface FormFieldMappingItem {
    field_key: string
    surrogate_field: string
}

export interface FormSurrogateFieldOption {
    value: string
    label: string
    is_critical?: boolean
}

export const DEFAULT_FORM_SURROGATE_FIELD_OPTIONS: FormSurrogateFieldOption[] = [
    { value: "full_name", label: "Full Name", is_critical: true },
    { value: "email", label: "Email", is_critical: true },
    { value: "phone", label: "Phone" },
    { value: "state", label: "State" },
    { value: "date_of_birth", label: "Date of Birth" },
    { value: "race", label: "Race" },
    { value: "height_ft", label: "Height (ft)" },
    { value: "weight_lb", label: "Weight (lb)" },
    { value: "is_age_eligible", label: "Age Eligible" },
    { value: "is_citizen_or_pr", label: "US Citizen/PR" },
    { value: "has_child", label: "Has Child" },
    { value: "is_non_smoker", label: "Non-Smoker" },
    { value: "has_surrogate_experience", label: "Surrogate Experience" },
    { value: "num_deliveries", label: "Number of Deliveries" },
    { value: "num_csections", label: "Number of C-Sections" },
    { value: "is_priority", label: "Priority" },
]

export interface FormTokenRead {
    token_id: string
    token: string
    expires_at: string
    application_url?: string | null
}

export interface FormTokenSendResponse {
    token_id: string
    token: string
    template_id: string
    email_log_id: string
    sent_at: string
    application_url?: string | null
}

export interface FormSubmissionFileRead {
    id: string
    filename: string
    content_type: string
    file_size: number
    quarantined: boolean
    scan_status: string
    field_key?: string | null
}

export interface FormSubmissionRead {
    id: string
    form_id: string
    surrogate_id?: string | null
    status: FormSubmissionStatus
    submitted_at: string
    reviewed_at?: string | null
    reviewed_by_user_id?: string | null
    review_notes?: string | null
    answers: JsonObject
    schema_snapshot?: FormSchema | null
    source_mode: FormLinkMode
    intake_link_id?: string | null
    intake_lead_id?: string | null
    match_status: SharedSubmissionOutcome
    match_reason?: string | null
    matched_at?: string | null
    files: FormSubmissionFileRead[]
}

export interface FormSubmissionPublicResponse {
    id: string
    status: FormSubmissionStatus
}

export interface FormPublicRead {
    form_id: string
    name: string
    description?: string | null
    form_schema: FormSchema
    max_file_size_bytes: number
    max_file_count: number
    allowed_mime_types?: string[] | null
}

export interface FormDraftPublicRead {
    answers: JsonObject
    started_at: string | null
    updated_at: string
}

export interface FormDraftWriteResponse {
    started_at: string | null
    updated_at: string
}

export interface FormIntakeLinkRead {
    id: string
    form_id: string
    slug: string
    campaign_name?: string | null
    event_name?: string | null
    utm_defaults?: Record<string, string> | null
    is_active: boolean
    expires_at?: string | null
    max_submissions?: number | null
    submissions_count: number
    intake_url?: string | null
    created_at: string
    updated_at: string
}

export interface FormIntakeLinkCreatePayload {
    campaign_name?: string | null
    event_name?: string | null
    expires_at?: string | null
    max_submissions?: number | null
    utm_defaults?: Record<string, string> | null
}

export interface FormIntakeLinkUpdatePayload extends FormIntakeLinkCreatePayload {
    is_active?: boolean
}

export interface FormDeliverySettings {
    default_application_email_template_id?: string | null
}

export interface FormSubmissionSharedResponse {
    id: string
    status: FormSubmissionStatus
    outcome: SharedSubmissionOutcome
    surrogate_id?: string | null
    intake_lead_id?: string | null
}

export interface FormIntakePublicRead {
    form_id: string
    intake_link_id: string
    name: string
    description?: string | null
    form_schema: FormSchema
    max_file_size_bytes: number
    max_file_count: number
    allowed_mime_types?: string[] | null
    campaign_name?: string | null
    event_name?: string | null
}

export interface MatchCandidateRead {
    id: string
    submission_id: string
    surrogate_id: string
    reason: string
    created_at: string
}

export interface ResolveSubmissionMatchPayload {
    surrogate_id?: string | null
    create_intake_lead?: boolean
    review_notes?: string | null
}

export interface RetrySubmissionMatchPayload {
    unlink_surrogate?: boolean
    unlink_intake_lead?: boolean
    rerun_auto_match?: boolean
    create_intake_lead_if_unmatched?: boolean
    review_notes?: string | null
}

export interface ResolveSubmissionMatchResponse {
    submission: FormSubmissionRead
    outcome: SharedSubmissionOutcome
    candidate_count: number
}

export interface IntakeLeadRead {
    id: string
    form_id?: string | null
    intake_link_id?: string | null
    full_name: string
    email?: string | null
    phone?: string | null
    date_of_birth?: string | null
    status: string
    promoted_surrogate_id?: string | null
    created_at: string
    updated_at: string
    promoted_at?: string | null
}

export interface PromoteIntakeLeadPayload {
    source?: string | null
    is_priority?: boolean
    assign_to_user?: boolean | null
}

export interface PromoteIntakeLeadResponse {
    intake_lead_id: string
    surrogate_id: string
    linked_submission_count: number
}

export interface FormDraftStatusRead {
    started_at: string | null
    updated_at: string
}

export interface ListFormSubmissionsParams {
    status?: FormSubmissionStatus
    match_status?: SharedSubmissionOutcome
    source_mode?: FormLinkMode
    limit?: number
}

export interface FormLogoRead {
    id: string
    logo_url: string
    filename: string
    content_type: string
    file_size: number
    created_at: string
}

export interface FormTemplateLibraryItem {
    id: string
    name: string
    description?: string | null
    published_at?: string | null
    updated_at: string
}

export interface FormTemplateLibraryDetail extends FormTemplateLibraryItem {
    schema_json?: FormSchema | null
    settings_json?: Record<string, unknown> | null
}

export interface FormTemplateUseRequest {
    name: string
    description?: string | null
}

export interface SubmissionDownloadResponse {
    download_url: string
    filename: string
}

export function listForms(): Promise<FormSummary[]> {
    return api.get<FormSummary[]>('/forms')
}

export function getForm(formId: string): Promise<FormRead> {
    return api.get<FormRead>(`/forms/${formId}`)
}

export function createForm(payload: FormCreatePayload): Promise<FormRead> {
    return api.post<FormRead>('/forms', payload)
}

export function updateForm(formId: string, payload: FormUpdatePayload): Promise<FormRead> {
    return api.patch<FormRead>(`/forms/${formId}`, payload)
}

export function deleteForm(formId: string): Promise<void> {
    return api.delete<void>(`/forms/${formId}`)
}

export function publishForm(formId: string): Promise<FormPublishResponse> {
    return api.post<FormPublishResponse>(`/forms/${formId}/publish`)
}

export function listFormMappings(formId: string): Promise<FormFieldMappingItem[]> {
    return api.get<FormFieldMappingItem[]>(`/forms/${formId}/mappings`)
}

type RawFormMappingOption = {
    value?: string
    key?: string
    label?: string
    name?: string
    is_critical?: boolean
    required?: boolean
}

function normalizeFormMappingOptions(payload: unknown): FormSurrogateFieldOption[] {
    if (!payload) return []
    const rawOptions = Array.isArray(payload)
        ? payload
        : typeof payload === "object" &&
            payload !== null &&
            "options" in payload &&
            Array.isArray((payload as { options?: unknown }).options)
            ? (payload as { options: unknown[] }).options
            : []

    const normalized = rawOptions.flatMap((raw) => {
        if (!raw || typeof raw !== "object") return []
        const option = raw as RawFormMappingOption
        const value = typeof option.value === "string" ? option.value : option.key
        if (!value) return []

        const label =
            typeof option.label === "string"
                ? option.label
                : typeof option.name === "string"
                    ? option.name
                    : value
        const isCritical =
            typeof option.is_critical === "boolean"
                ? option.is_critical
                : typeof option.required === "boolean"
                    ? option.required
                    : undefined

        return [{ value, label, ...(isCritical !== undefined ? { is_critical: isCritical } : {}) }]
    })

    return normalized
}

export async function listFormMappingOptions(): Promise<FormSurrogateFieldOption[]> {
    const endpointCandidates = ["/forms/mapping-options"]

    for (const endpoint of endpointCandidates) {
        try {
            const response = await api.get<unknown>(endpoint)
            const normalized = normalizeFormMappingOptions(response)
            if (normalized.length > 0) return normalized
        } catch {
            // Continue trying candidates; caller applies fallback defaults.
        }
    }

    return []
}

export function setFormMappings(formId: string, mappings: FormFieldMappingItem[]): Promise<FormFieldMappingItem[]> {
    return api.put<FormFieldMappingItem[]>(`/forms/${formId}/mappings`, { mappings })
}

// ============================================================================
// Platform Form Template Library
// ============================================================================

export function listFormTemplates(): Promise<FormTemplateLibraryItem[]> {
    return api.get<FormTemplateLibraryItem[]>(`/forms/templates`)
}

export function getFormTemplate(templateId: string): Promise<FormTemplateLibraryDetail> {
    return api.get<FormTemplateLibraryDetail>(`/forms/templates/${templateId}`)
}

export function createFormFromTemplate(
    templateId: string,
    payload: FormTemplateUseRequest
): Promise<FormRead> {
    return api.post<FormRead>(`/forms/templates/${templateId}/use`, payload)
}

export function deleteFormTemplate(templateId: string): Promise<void> {
    return api.delete<void>(`/forms/templates/${templateId}`)
}

export function createFormToken(
    formId: string,
    surrogateId: string,
    expiresInDays?: number,
    allowPurposeOverride?: boolean,
): Promise<FormTokenRead> {
    return api.post<FormTokenRead>(`/forms/${formId}/tokens`, {
        surrogate_id: surrogateId,
        expires_in_days: expiresInDays,
        allow_purpose_override: allowPurposeOverride ?? false,
    })
}

export function sendFormToken(
    formId: string,
    tokenId: string,
    templateId?: string | null,
    allowPurposeOverride?: boolean,
): Promise<FormTokenSendResponse> {
    return api.post<FormTokenSendResponse>(`/forms/${formId}/tokens/${tokenId}/send`, {
        template_id: templateId ?? null,
        allow_purpose_override: allowPurposeOverride ?? false,
    })
}

export function setDefaultSurrogateApplicationForm(formId: string): Promise<FormRead> {
    return api.post<FormRead>(`/forms/${formId}/set-default-surrogate-application`, {})
}

export function updateFormDeliverySettings(
    formId: string,
    payload: FormDeliverySettings,
): Promise<FormDeliverySettings> {
    return api.patch<FormDeliverySettings>(`/forms/${formId}/delivery-settings`, payload)
}

export function listFormIntakeLinks(
    formId: string,
    includeInactive = false,
): Promise<FormIntakeLinkRead[]> {
    const query = includeInactive ? "?include_inactive=true" : ""
    return api.get<FormIntakeLinkRead[]>(`/forms/${formId}/intake-links${query}`)
}

export function createFormIntakeLink(
    formId: string,
    payload: FormIntakeLinkCreatePayload,
): Promise<FormIntakeLinkRead> {
    return api.post<FormIntakeLinkRead>(`/forms/${formId}/intake-links`, payload)
}

export function updateFormIntakeLink(
    linkId: string,
    payload: FormIntakeLinkUpdatePayload,
): Promise<FormIntakeLinkRead> {
    return api.patch<FormIntakeLinkRead>(`/forms/intake-links/${linkId}`, payload)
}

export function rotateFormIntakeLink(linkId: string): Promise<FormIntakeLinkRead> {
    return api.post<FormIntakeLinkRead>(`/forms/intake-links/${linkId}/rotate`, {})
}

export function getSurrogateSubmission(formId: string, surrogateId: string): Promise<FormSubmissionRead> {
    return api.get<FormSubmissionRead>(`/forms/${formId}/surrogates/${surrogateId}/submission`)
}

export function listFormSubmissions(
    formId: string,
    params: ListFormSubmissionsParams = {},
): Promise<FormSubmissionRead[]> {
    const query = new URLSearchParams()
    if (params.status) query.set("status", params.status)
    if (params.match_status) query.set("match_status", params.match_status)
    if (params.source_mode) query.set("source_mode", params.source_mode)
    if (typeof params.limit === "number") query.set("limit", String(params.limit))
    const suffix = query.toString() ? `?${query.toString()}` : ""
    return api.get<FormSubmissionRead[]>(`/forms/${formId}/submissions${suffix}`)
}

export function approveSubmission(submissionId: string, reviewNotes?: string | null): Promise<FormSubmissionRead> {
    return api.post<FormSubmissionRead>(`/forms/submissions/${submissionId}/approve`, {
        review_notes: reviewNotes || null,
    })
}

export function rejectSubmission(submissionId: string, reviewNotes?: string | null): Promise<FormSubmissionRead> {
    return api.post<FormSubmissionRead>(`/forms/submissions/${submissionId}/reject`, {
        review_notes: reviewNotes || null,
    })
}

export function getPublicForm(token: string): Promise<FormPublicRead> {
    return api.get<FormPublicRead>(`/forms/public/${token}`)
}

export function getSharedPublicForm(slug: string): Promise<FormIntakePublicRead> {
    return api.get<FormIntakePublicRead>(`/forms/public/intake/${slug}`)
}

export function getPublicFormDraft(token: string): Promise<FormDraftPublicRead> {
    return api.get<FormDraftPublicRead>(`/forms/public/${token}/draft`)
}

export function getSharedPublicFormDraft(
    slug: string,
    draftSessionId: string,
): Promise<FormDraftPublicRead> {
    return api.get<FormDraftPublicRead>(`/forms/public/intake/${slug}/draft/${draftSessionId}`)
}

export function savePublicFormDraft(
    token: string,
    answers: JsonObject,
): Promise<FormDraftWriteResponse> {
    return api.put<FormDraftWriteResponse>(`/forms/public/${token}/draft`, { answers })
}

export function saveSharedPublicFormDraft(
    slug: string,
    draftSessionId: string,
    answers: JsonObject,
): Promise<FormDraftWriteResponse> {
    return api.put<FormDraftWriteResponse>(`/forms/public/intake/${slug}/draft/${draftSessionId}`, {
        answers,
    })
}

export function deletePublicFormDraft(token: string): Promise<void> {
    return api.delete<void>(`/forms/public/${token}/draft`)
}

export function deleteSharedPublicFormDraft(
    slug: string,
    draftSessionId: string,
): Promise<void> {
    return api.delete<void>(`/forms/public/intake/${slug}/draft/${draftSessionId}`)
}

export function getSurrogateDraftStatus(
    formId: string,
    surrogateId: string,
): Promise<FormDraftStatusRead> {
    return api.get<FormDraftStatusRead>(`/forms/${formId}/surrogates/${surrogateId}/draft`)
}

export function submitPublicForm(
    token: string,
    answers: JsonObject,
    files: File[] = [],
    fileFieldKeys?: string[]
): Promise<FormSubmissionPublicResponse> {
    const formData = new FormData()
    formData.append('answers', JSON.stringify(answers))
    files.forEach((file) => formData.append('files', file))
    if (fileFieldKeys) {
        formData.append('file_field_keys', JSON.stringify(fileFieldKeys))
    }
    return api.upload<FormSubmissionPublicResponse>(`/forms/public/${token}/submit`, formData)
}

export function submitSharedPublicForm(
    slug: string,
    answers: JsonObject,
    files: File[] = [],
    fileFieldKeys?: string[],
    challengeToken?: string | null
): Promise<FormSubmissionSharedResponse> {
    const formData = new FormData()
    formData.append('answers', JSON.stringify(answers))
    files.forEach((file) => formData.append('files', file))
    if (fileFieldKeys) {
        formData.append('file_field_keys', JSON.stringify(fileFieldKeys))
    }
    const options = challengeToken ? { headers: { "X-Intake-Challenge": challengeToken } } : undefined
    return api.upload<FormSubmissionSharedResponse>(`/forms/public/intake/${slug}/submit`, formData, options)
}

export function getSubmissionFileDownloadUrl(submissionId: string, fileId: string): Promise<SubmissionDownloadResponse> {
    return api.get<SubmissionDownloadResponse>(
        `/forms/submissions/${submissionId}/files/${fileId}/download`
    )
}

export function uploadSubmissionFile(
    submissionId: string,
    file: File,
    fieldKey?: string | null
): Promise<FormSubmissionFileRead> {
    const formData = new FormData()
    formData.append('file', file)
    if (fieldKey) {
        formData.append('field_key', fieldKey)
    }
    return api.upload<FormSubmissionFileRead>(
        `/forms/submissions/${submissionId}/files`,
        formData
    )
}

export function deleteSubmissionFile(submissionId: string, fileId: string): Promise<{ deleted: boolean }> {
    return api.delete<{ deleted: boolean }>(
        `/forms/submissions/${submissionId}/files/${fileId}`
    )
}

export function uploadFormLogo(file: File): Promise<FormLogoRead> {
    const formData = new FormData()
    formData.append('file', file)
    return api.upload<FormLogoRead>('/forms/logos', formData)
}

// Submission answer update types
export interface SubmissionAnswerUpdate {
    field_key: string
    value: unknown
}

export interface SubmissionAnswersUpdateResponse {
    submission: FormSubmissionRead
    surrogate_updates: string[]
}

export function updateSubmissionAnswers(
    submissionId: string,
    updates: SubmissionAnswerUpdate[]
): Promise<SubmissionAnswersUpdateResponse> {
    return api.patch<SubmissionAnswersUpdateResponse>(
        `/forms/submissions/${submissionId}/answers`,
        { updates }
    )
}

export function listSubmissionMatchCandidates(submissionId: string): Promise<MatchCandidateRead[]> {
    return api.get<MatchCandidateRead[]>(`/forms/submissions/${submissionId}/match-candidates`)
}

export function resolveSubmissionMatch(
    submissionId: string,
    payload: ResolveSubmissionMatchPayload
): Promise<ResolveSubmissionMatchResponse> {
    return api.post<ResolveSubmissionMatchResponse>(
        `/forms/submissions/${submissionId}/match/resolve`,
        payload
    )
}

export function retrySubmissionMatch(
    submissionId: string,
    payload: RetrySubmissionMatchPayload
): Promise<ResolveSubmissionMatchResponse> {
    return api.post<ResolveSubmissionMatchResponse>(
        `/forms/submissions/${submissionId}/match/retry`,
        payload
    )
}

export function getIntakeLead(leadId: string): Promise<IntakeLeadRead> {
    return api.get<IntakeLeadRead>(`/forms/intake-leads/${leadId}`)
}

export function promoteIntakeLead(
    leadId: string,
    payload: PromoteIntakeLeadPayload = {}
): Promise<PromoteIntakeLeadResponse> {
    return api.post<PromoteIntakeLeadResponse>(`/forms/intake-leads/${leadId}/promote`, payload)
}

export async function exportSubmissionPdf(submissionId: string): Promise<void> {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
    const url = `${baseUrl}/forms/submissions/${submissionId}/export`

    const response = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers: { ...getCsrfHeaders() },
    })

    if (!response.ok) {
        throw new Error(`Export failed (${response.status})`)
    }

    const contentType = response.headers.get('content-type') || ''
    if (!contentType.includes('application/pdf')) {
        const errorText = await response.text()
        throw new Error(errorText || 'Export failed (unexpected response)')
    }

    const buffer = await response.arrayBuffer()
    const headerBytes = new Uint8Array(buffer.slice(0, 4))
    const headerText = String.fromCharCode(...headerBytes)
    if (headerText !== '%PDF') {
        const errorText = new TextDecoder().decode(buffer)
        throw new Error(errorText || 'Export failed (invalid PDF)')
    }

    const blob = new Blob([buffer], { type: 'application/pdf' })
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = `application_${submissionId}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(objectUrl)
}
