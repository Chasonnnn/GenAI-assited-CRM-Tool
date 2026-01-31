/**
 * Forms API client
 */

import api from './index'
import { getCsrfHeaders } from '@/lib/csrf'
import type { JsonObject } from '../types/json'

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
    surrogate_field: string
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
    field_key?: string | null
}

export interface FormSubmissionRead {
    id: string
    form_id: string
    surrogate_id: string
    status: FormSubmissionStatus
    submitted_at: string
    reviewed_at?: string | null
    reviewed_by_user_id?: string | null
    review_notes?: string | null
    answers: JsonObject
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

export function createFormToken(formId: string, surrogateId: string, expiresInDays?: number): Promise<FormTokenRead> {
    return api.post<FormTokenRead>(`/forms/${formId}/tokens`, {
        surrogate_id: surrogateId,
        expires_in_days: expiresInDays,
    })
}

export function getSurrogateSubmission(formId: string, surrogateId: string): Promise<FormSubmissionRead> {
    return api.get<FormSubmissionRead>(`/forms/${formId}/surrogates/${surrogateId}/submission`)
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
