import api from "./index"

export type WorkflowMetricEventType =
    | "workflow_path_dashboard_viewed"
    | "workflow_path_unassigned_queue_viewed"
    | "workflow_path_surrogate_viewed"
    | "workflow_path_first_contact_logged"
    | "workflow_setup_started"
    | "workflow_setup_completed"

export interface WorkflowMetricEventPayload {
    event_type: WorkflowMetricEventType
    target_type?: string
    target_id?: string
    details?: Record<string, unknown>
}

export function recordWorkflowMetricEvent(payload: WorkflowMetricEventPayload): Promise<{ success: boolean }> {
    return api.post<{ success: boolean }>("/workflow-metrics/events", payload)
}
