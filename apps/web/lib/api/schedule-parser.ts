/**
 * Schedule Parser API client
 */

import api from './index'

// Types
export interface ProposedTask {
    title: string
    description: string | null
    due_date: string | null  // ISO format
    due_time: string | null  // HH:MM format
    task_type: string
    confidence: number
    dedupe_key: string
}

export interface ParseScheduleRequest {
    text: string
    // At least one entity ID must be provided
    surrogate_id?: string
    intended_parent_id?: string
    match_id?: string
    user_timezone?: string
}

export interface ParseScheduleResponse {
    proposed_tasks: ProposedTask[]
    warnings: string[]
    assumed_timezone: string
    assumed_reference_date: string
}

export interface BulkTaskItem {
    title: string
    description?: string | null
    due_date?: string | null
    due_time?: string | null
    task_type: string
    dedupe_key?: string | null
}

export interface BulkTaskCreateRequest {
    request_id: string
    // At least one entity ID must be provided
    surrogate_id?: string
    intended_parent_id?: string
    match_id?: string
    tasks: BulkTaskItem[]
}

export interface BulkTaskCreateResponse {
    success: boolean
    created: Array<{ task_id: string; title: string }>
    error?: string | null
}

// API functions
export async function parseSchedule(data: ParseScheduleRequest): Promise<ParseScheduleResponse> {
    return api.post<ParseScheduleResponse>('/ai/parse-schedule', data)
}

export async function createBulkTasks(data: BulkTaskCreateRequest): Promise<BulkTaskCreateResponse> {
    return api.post<BulkTaskCreateResponse>('/ai/create-bulk-tasks', data)
}
