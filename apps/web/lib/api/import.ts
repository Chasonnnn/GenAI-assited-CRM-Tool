/**
 * CSV Import API client
 */

import api from './index'

// Types
export interface ImportPreview {
    total_rows: number
    sample_rows: Array<Record<string, string>>
    detected_columns: string[]
    unmapped_columns: string[]
    duplicate_emails_db: number
    duplicate_emails_csv: number
    validation_errors: number
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

export interface ImportExecuteResponse {
    import_id: string
    message: string
}

// API functions
export async function previewImport(file: File): Promise<ImportPreview> {
    const formData = new FormData()
    formData.append('file', file)

    return api.post<ImportPreview>('/surrogates/import/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}

export async function executeImport(file: File): Promise<ImportExecuteResponse> {
    const formData = new FormData()
    formData.append('file', file)

    return api.post<ImportExecuteResponse>('/surrogates/import/execute', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}

export async function listImports(): Promise<ImportHistoryItem[]> {
    return api.get<ImportHistoryItem[]>('/surrogates/import')
}

export async function getImportDetails(importId: string): Promise<ImportDetail> {
    return api.get<ImportDetail>(`/surrogates/import/${importId}`)
}
