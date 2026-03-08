import { api } from '../api'
import type { ZapierStageBucket } from './zapier'

export interface MetaCrmDatasetEventMappingItem {
    stage_key: string
    event_name: string
    enabled: boolean
    bucket?: ZapierStageBucket | null
}

export interface MetaCrmDatasetSettings {
    dataset_id?: string | null
    access_token_configured: boolean
    enabled: boolean
    crm_name: string
    send_hashed_pii: boolean
    event_mapping: MetaCrmDatasetEventMappingItem[]
    test_event_code?: string | null
}

export interface UpdateMetaCrmDatasetSettingsRequest {
    dataset_id?: string | null
    access_token?: string | null
    enabled?: boolean
    crm_name?: string
    send_hashed_pii?: boolean
    event_mapping?: MetaCrmDatasetEventMappingItem[]
    test_event_code?: string | null
}

export interface MetaCrmDatasetOutboundTestRequest {
    stage_key?: string
    lead_id?: string
    fbc?: string | null
    test_event_code?: string | null
}

export interface MetaCrmDatasetOutboundTestResponse {
    status: string
    event_name: string
    event_id: string
    lead_id: string
}

export type MetaCrmDatasetEventStatus = 'queued' | 'delivered' | 'failed' | 'skipped'

export interface MetaCrmDatasetEvent {
    id: string
    source: string
    status: MetaCrmDatasetEventStatus
    reason?: string | null
    event_id?: string | null
    event_name?: string | null
    lead_id?: string | null
    stage_key?: string | null
    stage_slug?: string | null
    stage_label?: string | null
    surrogate_id?: string | null
    attempts: number
    last_error?: string | null
    created_at: string
    updated_at: string
    delivered_at?: string | null
    last_attempt_at?: string | null
    can_retry: boolean
}

export interface MetaCrmDatasetEventsResponse {
    items: MetaCrmDatasetEvent[]
    total: number
}

export interface MetaCrmDatasetEventsSummary {
    window_hours: number
    total_count: number
    queued_count: number
    delivered_count: number
    failed_count: number
    skipped_count: number
    actionable_skipped_count: number
    failure_rate: number
    skipped_rate: number
    failure_rate_alert: boolean
    skipped_rate_alert: boolean
    warning_messages: string[]
}

export interface MetaCrmDatasetEventsRequest {
    status?: MetaCrmDatasetEventStatus
    limit?: number
    offset?: number
}

export interface RetryMetaCrmDatasetEventRequest {
    reason?: string | null
}

export async function getMetaCrmDatasetSettings(): Promise<MetaCrmDatasetSettings> {
    return api.get<MetaCrmDatasetSettings>('/integrations/meta/crm-dataset/settings')
}

export async function updateMetaCrmDatasetSettings(
    payload: UpdateMetaCrmDatasetSettingsRequest,
): Promise<MetaCrmDatasetSettings> {
    return api.patch<MetaCrmDatasetSettings>('/integrations/meta/crm-dataset/settings', payload)
}

export async function sendMetaCrmDatasetOutboundTest(
    payload: MetaCrmDatasetOutboundTestRequest,
): Promise<MetaCrmDatasetOutboundTestResponse> {
    return api.post<MetaCrmDatasetOutboundTestResponse>('/integrations/meta/crm-dataset/test-outbound', payload)
}

export async function getMetaCrmDatasetEvents(
    params: MetaCrmDatasetEventsRequest = {},
): Promise<MetaCrmDatasetEventsResponse> {
    const searchParams = new URLSearchParams()
    if (params.status) {
        searchParams.set('status', params.status)
    }
    if (params.limit !== undefined) {
        searchParams.set('limit', String(params.limit))
    }
    if (params.offset !== undefined) {
        searchParams.set('offset', String(params.offset))
    }
    const query = searchParams.toString()
    return api.get<MetaCrmDatasetEventsResponse>(
        `/integrations/meta/crm-dataset/events${query ? `?${query}` : ''}`,
    )
}

export async function getMetaCrmDatasetEventsSummary(
    windowHours = 24,
): Promise<MetaCrmDatasetEventsSummary> {
    return api.get<MetaCrmDatasetEventsSummary>(
        `/integrations/meta/crm-dataset/events/summary?window_hours=${windowHours}`,
    )
}

export async function retryMetaCrmDatasetEvent(
    eventId: string,
    payload: RetryMetaCrmDatasetEventRequest = {},
): Promise<MetaCrmDatasetEvent> {
    return api.post<MetaCrmDatasetEvent>(`/integrations/meta/crm-dataset/events/${eventId}/retry`, payload)
}
