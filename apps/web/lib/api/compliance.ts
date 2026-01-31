/**
 * Compliance API client
 */

import api from './index'

export interface RetentionPolicy {
    id: string
    entity_type: string
    retention_days: number
    is_active: boolean
    created_by_user_id: string | null
    created_at: string
    updated_at: string
}

export interface RetentionPolicyUpsert {
    entity_type: string
    retention_days: number
    is_active: boolean
}

export interface LegalHold {
    id: string
    entity_type: string | null
    entity_id: string | null
    reason: string
    created_by_user_id: string | null
    created_at: string
    released_at: string | null
    released_by_user_id: string | null
}

export interface LegalHoldCreate {
    entity_type?: string | null
    entity_id?: string | null
    reason: string
}

export interface LegalHoldListParams {
    page?: number
    per_page?: number
}

export interface LegalHoldListResponse {
    items: LegalHold[]
    total: number
    page: number
    per_page: number
    pages: number
}

export interface PurgePreviewItem {
    entity_type: string
    count: number
}

export interface PurgePreviewResponse {
    items: PurgePreviewItem[]
}

export interface PurgeExecuteResponse {
    job_id: string
}

export async function listRetentionPolicies(): Promise<RetentionPolicy[]> {
    return api.get<RetentionPolicy[]>('/compliance/policies')
}

export async function upsertRetentionPolicy(
    data: RetentionPolicyUpsert
): Promise<RetentionPolicy> {
    return api.post<RetentionPolicy>('/compliance/policies', data)
}

export async function listLegalHolds(
    params: LegalHoldListParams = {}
): Promise<LegalHoldListResponse> {
    const searchParams = new URLSearchParams()
    if (params.page) searchParams.set('page', String(params.page))
    if (params.per_page) searchParams.set('per_page', String(params.per_page))
    const query = searchParams.toString()
    return api.get<LegalHoldListResponse>(`/compliance/legal-holds${query ? `?${query}` : ''}`)
}

export async function createLegalHold(data: LegalHoldCreate): Promise<LegalHold> {
    return api.post<LegalHold>('/compliance/legal-holds', data)
}

export async function releaseLegalHold(id: string): Promise<LegalHold> {
    return api.post<LegalHold>(`/compliance/legal-holds/${id}/release`, {})
}

export async function previewPurge(): Promise<PurgePreviewResponse> {
    return api.get<PurgePreviewResponse>('/compliance/purge-preview')
}

export async function executePurge(): Promise<PurgeExecuteResponse> {
    return api.post<PurgeExecuteResponse>('/compliance/purge-execute', {})
}
