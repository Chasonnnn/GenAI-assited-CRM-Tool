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
}

/**
 * Get upcoming tasks and meetings for dashboard widget.
 */
export async function getUpcoming(params: GetUpcomingParams = {}): Promise<UpcomingResponse> {
    const searchParams = new URLSearchParams()
    if (params.days) searchParams.set('days', params.days.toString())
    if (params.include_overdue !== undefined) searchParams.set('include_overdue', params.include_overdue.toString())
    const query = searchParams.toString()
    return api.get<UpcomingResponse>(`/dashboard/upcoming${query ? `?${query}` : ''}`)
}
