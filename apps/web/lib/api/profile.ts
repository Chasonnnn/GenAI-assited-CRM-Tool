/**
 * Profile Card API client
 */

import api from './index'
import type { FormSchema } from './forms'

export interface ProfileDataResponse {
    base_submission_id: string | null
    base_answers: Record<string, unknown>
    overrides: Record<string, unknown>
    hidden_fields: string[]
    merged_view: Record<string, unknown>
    schema_snapshot: FormSchema | null
}

export interface SyncDiffItem {
    field_key: string
    old_value: unknown
    new_value: unknown
}

export interface SyncDiffResponse {
    staged_changes: SyncDiffItem[]
    latest_submission_id: string | null
}

export interface ProfileOverridesUpdate {
    overrides: Record<string, unknown>
    new_base_submission_id?: string | null
}

export interface ProfileHiddenUpdate {
    field_key: string
    hidden: boolean
}

export function getProfile(caseId: string): Promise<ProfileDataResponse> {
    return api.get<ProfileDataResponse>(`/cases/${caseId}/profile`)
}

export function syncProfile(caseId: string): Promise<SyncDiffResponse> {
    return api.post<SyncDiffResponse>(`/cases/${caseId}/profile/sync`)
}

export function saveProfileOverrides(
    caseId: string,
    overrides: Record<string, unknown>,
    newBaseSubmissionId?: string | null
): Promise<{ status: string }> {
    return api.put<{ status: string }>(`/cases/${caseId}/profile/overrides`, {
        overrides,
        new_base_submission_id: newBaseSubmissionId || null,
    })
}

export function toggleProfileHiddenField(
    caseId: string,
    fieldKey: string,
    hidden: boolean
): Promise<{ status: string; field_key: string; hidden: boolean }> {
    return api.post<{ status: string; field_key: string; hidden: boolean }>(
        `/cases/${caseId}/profile/hidden`,
        { field_key: fieldKey, hidden }
    )
}

export async function exportProfilePdf(caseId: string): Promise<void> {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
    const url = `${baseUrl}/cases/${caseId}/profile/export`

    const response = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
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
    link.download = `profile_${caseId}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(objectUrl)
}
