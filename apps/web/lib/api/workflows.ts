/**
 * Workflow API client for automation workflows.
 */

import api from './index'
import type { JsonObject, JsonValue } from '../types/json'

// =============================================================================
// Types
// =============================================================================

export interface Workflow {
    id: string
    name: string
    description: string | null
    icon: string
    schema_version: number
    trigger_type: string
    trigger_config: JsonObject
    conditions: Condition[]
    condition_logic: "AND" | "OR"
    actions: ActionConfig[]
    is_enabled: boolean
    scope: WorkflowScope
    owner_user_id: string | null
    owner_name: string | null
    run_count: number
    last_run_at: string | null
    last_error: string | null
    created_by_name: string | null
    updated_by_name: string | null
    created_at: string
    updated_at: string
    can_edit?: boolean
}

export type WorkflowScope = 'org' | 'personal'

export interface WorkflowListItem {
    id: string
    name: string
    description: string | null
    icon: string
    trigger_type: string
    is_enabled: boolean
    run_count: number
    last_run_at: string | null
    last_error: string | null
    scope: WorkflowScope
    owner_user_id: string | null
    owner_name: string | null
    created_at: string
    can_edit?: boolean
}

export interface Condition {
    field: string
    operator: string
    value: JsonValue
}

export interface ActionConfig {
    action_type: string
    [key: string]: JsonValue
}

export interface WorkflowCreate {
    name: string
    description?: string
    icon?: string
    trigger_type: string
    trigger_config?: JsonObject
    conditions?: Condition[]
    condition_logic?: "AND" | "OR"
    actions: ActionConfig[]
    is_enabled?: boolean
    scope?: WorkflowScope
}

export interface WorkflowUpdate {
    name?: string
    description?: string
    icon?: string
    trigger_type?: string
    trigger_config?: JsonObject
    conditions?: Condition[]
    condition_logic?: "AND" | "OR"
    actions?: ActionConfig[]
    is_enabled?: boolean
}

export interface WorkflowExecution {
    id: string
    workflow_id: string
    event_id: string
    depth: number
    event_source: string
    entity_type: string
    entity_id: string
    trigger_event: JsonObject
    matched_conditions: boolean
    actions_executed: ActionResult[]
    status: "success" | "partial" | "failed" | "skipped" | "paused" | "canceled" | "expired"
    error_message: string | null
    duration_ms: number | null
    executed_at: string
}

export interface ActionResult {
    success: boolean
    action_type?: string
    description?: string
    error?: string
    [key: string]: JsonValue
}

export interface WorkflowStats {
    total_workflows: number
    enabled_workflows: number
    total_executions_24h: number
    success_rate_24h: number
    by_trigger_type: Record<string, number>
}

export interface WorkflowOptions {
    trigger_types: { value: string; label: string; description: string }[]
    action_types: { value: string; label: string; description: string }[]
    action_types_by_trigger?: Record<string, string[]>
    trigger_entity_types?: Record<string, string>
    condition_operators: { value: string; label: string }[]
    condition_fields: string[]
    update_fields: string[]
    email_variables: string[]
    email_templates: { id: string; name: string }[]
    users: { id: string; display_name: string }[]
    queues: { id: string; name: string }[]
    statuses: { id?: string; value: string; label: string; is_active?: boolean }[]
    forms?: { id: string; name: string }[]
}

export interface WorkflowTestRequest {
    entity_id: string
    entity_type?: string
}

export interface WorkflowTestResponse {
    would_trigger: boolean
    conditions_matched: boolean
    conditions_evaluated: {
        field: string
        operator: string
        expected: unknown
        actual: string
        result: boolean
    }[]
    actions_preview: {
        action_type: string
        description: string
    }[]
}

export interface UserWorkflowPreference {
    id: string
    workflow_id: string
    workflow_name: string
    is_opted_out: boolean
}

// =============================================================================
// API Functions
// =============================================================================

export interface ListWorkflowsParams {
    enabled_only?: boolean
    trigger_type?: string
    scope?: WorkflowScope | null
}

export async function listWorkflows(params?: ListWorkflowsParams): Promise<WorkflowListItem[]> {
    const searchParams = new URLSearchParams()
    if (params?.enabled_only) searchParams.set("enabled_only", "true")
    if (params?.trigger_type) searchParams.set("trigger_type", params.trigger_type)
    if (params?.scope) searchParams.set("scope", params.scope)

    const query = searchParams.toString()
    return api.get<WorkflowListItem[]>(`/workflows${query ? `?${query}` : ""}`)
}

export async function getWorkflow(id: string): Promise<Workflow> {
    return api.get<Workflow>(`/workflows/${id}`)
}

export async function createWorkflow(data: WorkflowCreate): Promise<Workflow> {
    return api.post<Workflow>("/workflows", data)
}

export async function updateWorkflow(id: string, data: WorkflowUpdate): Promise<Workflow> {
    return api.patch<Workflow>(`/workflows/${id}`, data)
}

export async function deleteWorkflow(id: string): Promise<void> {
    return api.delete(`/workflows/${id}`)
}

export async function toggleWorkflow(id: string): Promise<Workflow> {
    return api.post<Workflow>(`/workflows/${id}/toggle`)
}

export async function duplicateWorkflow(id: string): Promise<Workflow> {
    return api.post<Workflow>(`/workflows/${id}/duplicate`)
}

export async function testWorkflow(
    id: string,
    entityId: string,
    entityType?: string
): Promise<WorkflowTestResponse> {
    return api.post<WorkflowTestResponse>(`/workflows/${id}/test`, {
        entity_id: entityId,
        ...(entityType ? { entity_type: entityType } : {}),
    })
}

export async function getWorkflowStats(): Promise<WorkflowStats> {
    return api.get<WorkflowStats>("/workflows/stats")
}

export async function getWorkflowOptions(workflowScope?: WorkflowScope): Promise<WorkflowOptions> {
    const searchParams = new URLSearchParams()
    if (workflowScope) searchParams.set("workflow_scope", workflowScope)
    const query = searchParams.toString()
    return api.get<WorkflowOptions>(`/workflows/options${query ? `?${query}` : ""}`)
}

export async function listExecutions(
    workflowId: string,
    params?: { limit?: number; offset?: number }
): Promise<{ items: WorkflowExecution[]; total: number }> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set("limit", String(params.limit))
    if (params?.offset) searchParams.set("offset", String(params.offset))

    const query = searchParams.toString()
    return api.get<{ items: WorkflowExecution[]; total: number }>(`/workflows/${workflowId}/executions${query ? `?${query}` : ""}`)
}

export async function getUserPreferences(): Promise<UserWorkflowPreference[]> {
    return api.get<UserWorkflowPreference[]>("/workflows/me/preferences")
}

export async function updateUserPreference(
    workflowId: string,
    isOptedOut: boolean
): Promise<UserWorkflowPreference> {
    return api.patch<UserWorkflowPreference>(`/workflows/me/preferences/${workflowId}`, { is_opted_out: isOptedOut })
}
