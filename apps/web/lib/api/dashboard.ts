/**
 * API client for dashboard widgets.
 */

import api from './index'

// =============================================================================
// Types
// =============================================================================

export interface UpcomingTask {
    id: string
    type: 'task'
    title: string
    time: string | null  // HH:MM format or null for all-day
    surrogate_id: string | null
    surrogate_number: string | null
    date: string  // YYYY-MM-DD
    is_overdue: boolean
    task_type: string
}

export interface UpcomingMeeting {
    id: string
    type: 'meeting'
    title: string
    time: string | null  // HH:MM format
    surrogate_id: string | null
    surrogate_number: string | null
    date: string  // YYYY-MM-DD
    is_overdue: boolean
    join_url: string
}

export interface UpcomingResponse {
    tasks: UpcomingTask[]
    meetings: UpcomingMeeting[]
}

// Unified type for widget
export type UpcomingItem =
    | (UpcomingTask & { type: 'task' })
    | (UpcomingMeeting & { type: 'meeting' })

// =============================================================================
// API Functions
// =============================================================================

export interface GetUpcomingParams {
    days?: number
    include_overdue?: boolean
    pipeline_id?: string
    assignee_id?: string
}

/**
 * Get upcoming tasks and meetings for dashboard widget.
 */
export async function getUpcoming(params: GetUpcomingParams = {}): Promise<UpcomingResponse> {
    const searchParams = new URLSearchParams()
    if (params.days) searchParams.set('days', params.days.toString())
    if (params.include_overdue !== undefined) searchParams.set('include_overdue', params.include_overdue.toString())
    if (params.pipeline_id) searchParams.set('pipeline_id', params.pipeline_id)
    if (params.assignee_id) searchParams.set('assignee_id', params.assignee_id)
    const query = searchParams.toString()
    return api.get<UpcomingResponse>(`/dashboard/upcoming${query ? `?${query}` : ''}`)
}

// =============================================================================
// Attention Items
// =============================================================================

export interface UnreachedLead {
    id: string
    surrogate_number: string
    stage_label: string
    days_since_contact: number
    created_at: string
}

export interface OverdueTaskItem {
    id: string
    title: string
    due_date: string | null
    days_overdue: number
    surrogate_id: string | null
}

export interface StuckSurrogate {
    id: string
    surrogate_number: string
    stage_label: string
    days_in_stage: number
    last_stage_change: string | null
}

export interface AttentionResponse {
    unreached_leads: UnreachedLead[]
    unreached_count: number
    overdue_tasks: OverdueTaskItem[]
    overdue_count: number
    stuck_surrogates: StuckSurrogate[]
    stuck_count: number
    total_count: number
}

export interface GetAttentionParams {
    days_unreached?: number | undefined
    days_stuck?: number | undefined
    pipeline_id?: string | undefined
    assignee_id?: string | undefined
    limit?: number | undefined
}

/**
 * Get attention items for dashboard KPI card.
 */
export async function getAttention(params: GetAttentionParams = {}): Promise<AttentionResponse> {
    const searchParams = new URLSearchParams()
    if (params.days_unreached) searchParams.set('days_unreached', params.days_unreached.toString())
    if (params.days_stuck) searchParams.set('days_stuck', params.days_stuck.toString())
    if (params.pipeline_id) searchParams.set('pipeline_id', params.pipeline_id)
    if (params.assignee_id) searchParams.set('assignee_id', params.assignee_id)
    if (params.limit) searchParams.set('limit', params.limit.toString())
    const query = searchParams.toString()
    return api.get<AttentionResponse>(`/dashboard/attention${query ? `?${query}` : ''}`)
}
