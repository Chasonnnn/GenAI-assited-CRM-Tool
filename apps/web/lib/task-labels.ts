import type { TaskLinkedType } from "@/lib/api/tasks"
import type { TaskFormData } from "@/lib/types/task"
import { createSelectLabelGetter, getSelectLabel, toSelectOptions } from "@/lib/select-labels"

type EditableTaskType = TaskFormData["task_type"]

/** Types a user can pick when creating or editing a task, in menu order. */
export const TASK_TYPE_LABELS: Record<EditableTaskType, string> = {
    meeting: "Meeting",
    follow_up: "Follow Up",
    contact: "Contact",
    review: "Review",
    medication: "Medication",
    exam: "Exam",
    appointment: "Appointment",
    other: "Other",
}

export const TASK_TYPE_OPTIONS = toSelectOptions(TASK_TYPE_LABELS)

// Workflow approvals are created by automations and never offered in the type menu.
const TASK_TYPE_DISPLAY_LABELS: Record<string, string> = {
    ...TASK_TYPE_LABELS,
    workflow_approval: "Approval",
}

export function isEditableTaskType(value: unknown): value is EditableTaskType {
    return typeof value === "string" && Object.prototype.hasOwnProperty.call(TASK_TYPE_LABELS, value)
}

/** Type select triggers and the task list type column. */
export function getTaskTypeLabel(value: string | null | undefined): string {
    return getSelectLabel(value, TASK_TYPE_DISPLAY_LABELS, { emptyLabel: "Select type", unknownLabel: "Other" })
}

export type TaskStatusFilter = "open" | "completed" | "all"

export const TASK_STATUS_FILTER_LABELS: Record<TaskStatusFilter, string> = {
    open: "Open",
    completed: "Completed",
    all: "All Statuses",
}

export const TASK_STATUS_FILTER_OPTIONS = toSelectOptions(TASK_STATUS_FILTER_LABELS)

export function isTaskStatusFilter(value: unknown): value is TaskStatusFilter {
    return typeof value === "string" && Object.prototype.hasOwnProperty.call(TASK_STATUS_FILTER_LABELS, value)
}

export const getTaskStatusFilterLabel = createSelectLabelGetter(TASK_STATUS_FILTER_LABELS, {
    emptyLabel: "Open",
    unknownLabel: "Open",
})

export type TaskDueFilter = "all" | "overdue" | "today" | "week"

export const TASK_DUE_FILTER_LABELS: Record<Exclude<TaskDueFilter, "all">, string> = {
    overdue: "Overdue",
    today: "Due today",
    week: "Due this week",
}

export const TASK_DUE_FILTER_OPTIONS = toSelectOptions(TASK_DUE_FILTER_LABELS)

export function isTaskDueFilter(value: unknown): value is TaskDueFilter {
    return value === "all" || (typeof value === "string" && Object.prototype.hasOwnProperty.call(TASK_DUE_FILTER_LABELS, value))
}

export const getTaskDueFilterLabel = createSelectLabelGetter(TASK_DUE_FILTER_LABELS, {
    emptyLabel: "Any Due Date",
    allValue: "all",
    unknownLabel: "Any Due Date",
})

export const TASK_LINKED_TYPE_LABELS: Record<TaskLinkedType, string> = {
    surrogate: "Surrogates",
    intended_parent: "Intended Parents",
    donor: "Donors",
    none: "No linked record",
}

export const TASK_LINKED_TYPE_OPTIONS = toSelectOptions(TASK_LINKED_TYPE_LABELS)

export function isTaskLinkedType(value: unknown): value is TaskLinkedType {
    return typeof value === "string" && Object.prototype.hasOwnProperty.call(TASK_LINKED_TYPE_LABELS, value)
}

export const getTaskLinkedTypeLabel = createSelectLabelGetter(TASK_LINKED_TYPE_LABELS, {
    emptyLabel: "All Records",
    allValue: "all",
    unknownLabel: "All Records",
})
