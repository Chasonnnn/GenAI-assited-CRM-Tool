/**
 * Profile Card API client
 */

import api from './index'
import { getCsrfHeaders } from '@/lib/csrf'
import type { FormSchema } from './forms'
import type { JsonObject, JsonValue } from '../types/json'

export interface ProfileDataResponse {
    base_submission_id: string | null
    base_answers: JsonObject
    overrides: JsonObject
    hidden_fields: string[]
    merged_view: JsonObject
    schema_snapshot: FormSchema | null
    header_name_override?: string | null
    header_note?: string | null
    custom_qas?: ProfileCustomQa[]
}

export interface ProfileCustomQa {
    [key: string]: JsonValue
    id: string
    section_key: string
    question: string
    answer: string
    order: number
}

export interface SyncDiffItem {
    field_key: string
    old_value: JsonValue
    new_value: JsonValue
}

export interface SyncDiffResponse {
    staged_changes: SyncDiffItem[]
    latest_submission_id: string | null
}

export interface ProfileOverridesUpdate {
    overrides: JsonObject
    new_base_submission_id?: string | null
}

export interface ProfileHiddenUpdate {
    field_key: string
    hidden: boolean
}

export function getProfile(surrogateId: string): Promise<ProfileDataResponse> {
    return api.get<ProfileDataResponse>(`/surrogates/${surrogateId}/profile`)
}

export function syncProfile(surrogateId: string): Promise<SyncDiffResponse> {
    return api.post<SyncDiffResponse>(`/surrogates/${surrogateId}/profile/sync`)
}

export function saveProfileOverrides(
    surrogateId: string,
    overrides: JsonObject,
    newBaseSubmissionId?: string | null
): Promise<{ status: string }> {
    return api.put<{ status: string }>(`/surrogates/${surrogateId}/profile/overrides`, {
        overrides,
        new_base_submission_id: newBaseSubmissionId || null,
    })
}

export function toggleProfileHiddenField(
    surrogateId: string,
    fieldKey: string,
    hidden: boolean
): Promise<{ status: string; field_key: string; hidden: boolean }> {
    return api.post<{ status: string; field_key: string; hidden: boolean }>(
        `/surrogates/${surrogateId}/profile/hidden`,
        { field_key: fieldKey, hidden }
    )
}

export async function exportProfilePdf(surrogateId: string): Promise<void> {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
    const url = `${baseUrl}/surrogates/${surrogateId}/profile/export`

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
    link.download = `profile_${surrogateId}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(objectUrl)
}
