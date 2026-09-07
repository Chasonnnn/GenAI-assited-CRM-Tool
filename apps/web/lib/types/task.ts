export type { TaskListItem } from "../api/tasks"

import type { TaskRecurrence } from "@/lib/utils/task-recurrence"

export interface TaskFormData {
    title: string
    description?: string
    task_type: "meeting" | "follow_up" | "contact" | "review" | "medication" | "exam" | "appointment" | "other"
    due_date?: string
    due_time?: string
    recurrence: TaskRecurrence
    repeat_until?: string
    surrogate_id: string | null
    intended_parent_id: string | null
    donor_id: string | null
}
