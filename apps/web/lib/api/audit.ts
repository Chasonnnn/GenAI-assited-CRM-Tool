/**
 * Audit Log API client
 */

import api from './index'

// Types
export interface AuditLogEntry {
    id: string
    event_type: string
    actor_user_id: string | null
    actor_name: string | null
    target_type: string | null
    target_id: string | null
    details: Record<string, unknown> | null
    ip_address: string | null
    created_at: string
}

export interface AuditLogListResponse {
    items: AuditLogEntry[]
    total: number
    page: number
    per_page: number
}

export interface AuditLogFilters {
    page?: number
    per_page?: number
    event_type?: string
    actor_user_id?: string
    start_date?: string
    end_date?: string
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
    return api.get<AuditLogListResponse>(`/audit${query ? `?${query}` : ''}`)
}

export async function listEventTypes(): Promise<string[]> {
    return api.get<string[]>('/audit/event-types')
}
