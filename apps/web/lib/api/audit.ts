/**
 * Audit Log API client
 */

import api from './index'
import type { JsonObject } from '../types/json'

// Types
export interface AuditLogEntry {
    id: string
    event_type: string
    actor_user_id: string | null
    actor_name: string | null
    target_type: string | null
    target_id: string | null
    details: JsonObject | null
    ip_address: string | null
    created_at: string
}

export interface AuditLogListResponse {
    items: AuditLogEntry[]
    total: number
    page: number
    per_page: number
}

export interface AIAuditActivity {
    counts: Record<string, number>
    recent: AuditLogEntry[]
}

export interface AuditLogFilters {
    page?: number
    per_page?: number
    event_type?: string
    actor_user_id?: string
    start_date?: string
    end_date?: string
}

export interface AuditExportJob {
    id: string
    status: string
    export_type: string
    format: string
    redact_mode: string
    date_range_start: string
    date_range_end: string
    record_count: number | null
    error_message: string | null
    created_at: string
    completed_at: string | null
    download_url: string | null
}

export interface AuditExportCreate {
    start_date: string
    end_date: string
    format: 'csv' | 'json'
    redact_mode: 'redacted' | 'full'
    acknowledgment?: string
}

// API functions
export async function listAuditLogs(filters: AuditLogFilters = {}): Promise<AuditLogListResponse> {
    const params = new URLSearchParams()
    if (filters.page) params.set('page', filters.page.toString())
    if (filters.per_page) params.set('per_page', filters.per_page.toString())
    if (filters.event_type) params.set('event_type', filters.event_type)
    if (filters.actor_user_id) params.set('actor_user_id', filters.actor_user_id)
    if (filters.start_date) params.set('start_date', filters.start_date)
    if (filters.end_date) params.set('end_date', filters.end_date)

    const query = params.toString()
    const path = query ? `/audit/?${query}` : '/audit/'
    return api.get<AuditLogListResponse>(path)
}

export async function listEventTypes(): Promise<string[]> {
    return api.get<string[]>('/audit/event-types')
}

export async function getAIAuditActivity(hours: number = 24): Promise<AIAuditActivity> {
    const data = await api.get<{ counts_24h: Record<string, number>; recent: AuditLogEntry[] }>(`/audit/ai-activity?hours=${hours}`)
    // Normalize response field name
    return { counts: data.counts_24h, recent: data.recent }
}

export async function listAuditExports(): Promise<{ items: AuditExportJob[] }> {
    return api.get<{ items: AuditExportJob[] }>('/audit/exports')
}

export async function getAuditExport(id: string): Promise<AuditExportJob> {
    return api.get<AuditExportJob>(`/audit/exports/${id}`)
}

export async function createAuditExport(data: AuditExportCreate): Promise<AuditExportJob> {
    return api.post<AuditExportJob>('/audit/exports', data)
}
