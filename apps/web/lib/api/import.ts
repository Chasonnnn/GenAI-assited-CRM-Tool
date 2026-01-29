/**
 * CSV Import API client (enhanced preview + approval flow)
 */

import api from './index'

export type ColumnAction = 'map' | 'metadata' | 'custom' | 'ignore'
export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'none'

export interface ColumnSuggestion {
    csv_column: string
    suggested_field: string | null
    confidence: number
    confidence_level: ConfidenceLevel
    transformation: string | null
    sample_values: string[]
    reason: string
    warnings: string[]
    default_action: ColumnAction | null
    needs_inversion: boolean
}

export interface EnhancedImportPreview {
    import_id: string
    total_rows: number
    sample_rows: Array<Record<string, string>>
    detected_encoding: string
    detected_delimiter: string
    has_header: boolean
    column_suggestions: ColumnSuggestion[]
    matched_count: number
    unmatched_count: number
    matching_templates: Array<{ id: string; name: string; match_score: number }>
    available_fields: string[]
    duplicate_emails_db: number
    duplicate_emails_csv: number
    validation_errors: number
    date_ambiguity_warnings: Array<Record<string, unknown>>
    ai_available: boolean
}

export interface ColumnMappingItem {
    csv_column: string
    surrogate_field: string | null
    transformation: string | null
    action: ColumnAction
    custom_field_key?: string | null
}

export interface ImportHistoryItem {
    id: string
    filename: string
    status: string
    total_rows: number
    imported_count: number | null
    skipped_count: number | null
    error_count: number | null
    created_at: string
    completed_at: string | null
}

export interface ImportDetail extends ImportHistoryItem {
    errors: Array<{ row: number; errors: string[] }> | null
}

export interface ImportSubmitResponse {
    import_id: string
    status: string
    deduplication_stats?: Record<string, unknown>
    message?: string
}

export interface ImportApprovalResponse {
    import_id: string
    status: string
    message?: string
    rejection_reason?: string
}

export interface DeduplicationStats {
    total: number
    new_records: number
    duplicates: Array<{ email?: string; existing_id?: string }>
}

export interface ImportApprovalItem {
    id: string
    filename: string
    status: string
    total_rows: number
    created_at: string
    created_by_name: string | null
    deduplication_stats: DeduplicationStats | null
    column_mapping_snapshot: ColumnMappingItem[] | null
    backdate_created_at?: boolean
}

export interface AiMapRequest {
    unmatched_columns: string[]
    sample_values: Record<string, string[]>
}

export interface AiMapResponse {
    suggestions: ColumnSuggestion[]
}

export async function previewImport(file: File): Promise<EnhancedImportPreview> {
    const formData = new FormData()
    formData.append('file', file)

    return api.post<EnhancedImportPreview>('/surrogates/import/preview/enhanced', formData)
}

export async function submitImport(
    importId: string,
    payload: {
        column_mappings: ColumnMappingItem[]
        unknown_column_behavior?: 'ignore' | 'metadata' | 'warn'
        save_as_template_name?: string | null
        backdate_created_at?: boolean
    }
): Promise<ImportSubmitResponse> {
    return api.post<ImportSubmitResponse>(`/surrogates/import/${importId}/submit`, payload)
}

export async function approveImport(importId: string): Promise<ImportApprovalResponse> {
    return api.post<ImportApprovalResponse>(`/surrogates/import/${importId}/approve`)
}

export async function rejectImport(importId: string, reason: string): Promise<ImportApprovalResponse> {
    return api.post<ImportApprovalResponse>(`/surrogates/import/${importId}/reject`, { reason })
}

export async function listPendingImportApprovals(): Promise<ImportApprovalItem[]> {
    return api.get<ImportApprovalItem[]>('/surrogates/import/pending')
}

export async function aiMapColumns(payload: AiMapRequest): Promise<AiMapResponse> {
    return api.post<AiMapResponse>('/surrogates/import/ai-map', payload)
}

export async function listImports(): Promise<ImportHistoryItem[]> {
    return api.get<ImportHistoryItem[]>('/surrogates/import')
}

export async function getImportDetails(importId: string): Promise<ImportDetail> {
    return api.get<ImportDetail>(`/surrogates/import/${importId}`)
}
