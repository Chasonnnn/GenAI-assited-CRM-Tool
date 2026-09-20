const WORKFLOW_EXECUTION_STATUS_LABELS = {
    running: "Running",
    success: "Success",
    failed: "Failed",
    partial: "Partial",
    skipped: "Skipped",
    paused: "Paused",
    canceled: "Canceled",
    expired: "Expired",
} as const

export type WorkflowExecutionStatus = keyof typeof WORKFLOW_EXECUTION_STATUS_LABELS

export function getWorkflowExecutionStatusLabel(status: string): string {
    return WORKFLOW_EXECUTION_STATUS_LABELS[status as WorkflowExecutionStatus] ?? status
}
