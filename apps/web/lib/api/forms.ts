/**
 * Forms API client
 */

import api from './index'

export type FormStatus = 'draft' | 'published' | 'archived'
export type FormSubmissionStatus = 'pending_review' | 'approved' | 'rejected'

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

export interface FormField {
    key: string
    label: string
    type: FieldType
    required?: boolean
    options?: FormFieldOption[] | null
    validation?: FormFieldValidation | null
    help_text?: string | null
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
}

export interface FormCreatePayload {
    name: string
    description?: string | null
    form_schema?: FormSchema | null
    max_file_size_bytes?: number | null
    max_file_count?: number | null
    allowed_mime_types?: string[] | null
}

export interface FormUpdatePayload {
    name?: string | null
    description?: string | null
    form_schema?: FormSchema | null
    max_file_size_bytes?: number | null
    max_file_count?: number | null
    allowed_mime_types?: string[] | null
}

export interface FormPublishResponse {
    id: string
    status: FormStatus
    published_at: string
}

export interface FormFieldMappingItem {
    field_key: string
    case_field: string
}

export interface FormTokenRead {
    token: string
    expires_at: string
}

export interface FormSubmissionFileRead {
    id: string
    filename: string
    content_type: string
    file_size: number
    quarantined: boolean
    scan_status: string
}

export interface FormSubmissionRead {
    id: string
    form_id: string
    case_id: string
    status: FormSubmissionStatus
    submitted_at: string
    reviewed_at?: string | null
    reviewed_by_user_id?: string | null
    review_notes?: string | null
    answers: Record<string, unknown>
    schema_snapshot?: FormSchema | null
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

export interface FormLogoRead {
    id: string
    logo_url: string
    filename: string
    content_type: string
    file_size: number
    created_at: string
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

export function publishForm(formId: string): Promise<FormPublishResponse> {
    return api.post<FormPublishResponse>(`/forms/${formId}/publish`)
}

export function listFormMappings(formId: string): Promise<FormFieldMappingItem[]> {
    return api.get<FormFieldMappingItem[]>(`/forms/${formId}/mappings`)
}

export function setFormMappings(formId: string, mappings: FormFieldMappingItem[]): Promise<FormFieldMappingItem[]> {
    return api.put<FormFieldMappingItem[]>(`/forms/${formId}/mappings`, { mappings })
}

export function createFormToken(formId: string, caseId: string, expiresInDays?: number): Promise<FormTokenRead> {
    return api.post<FormTokenRead>(`/forms/${formId}/tokens`, {
        case_id: caseId,
        expires_in_days: expiresInDays,
    })
}

export function getCaseSubmission(formId: string, caseId: string): Promise<FormSubmissionRead> {
    return api.get<FormSubmissionRead>(`/forms/${formId}/cases/${caseId}/submission`)
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

export function submitPublicForm(
    token: string,
    answers: Record<string, unknown>,
    files: File[] = []
): Promise<FormSubmissionPublicResponse> {
    const formData = new FormData()
    formData.append('answers', JSON.stringify(answers))
    files.forEach((file) => formData.append('files', file))
    return api.upload<FormSubmissionPublicResponse>(`/forms/public/${token}/submit`, formData)
}

export function getSubmissionFileDownloadUrl(submissionId: string, fileId: string): Promise<SubmissionDownloadResponse> {
    return api.get<SubmissionDownloadResponse>(
        `/forms/submissions/${submissionId}/files/${fileId}/download`
    )
}

export function uploadFormLogo(file: File): Promise<FormLogoRead> {
    const formData = new FormData()
    formData.append('file', file)
    return api.upload<FormLogoRead>('/forms/logos', formData)
}
