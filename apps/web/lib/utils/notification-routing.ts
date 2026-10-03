import type { Notification } from "@/lib/api/notifications"

type NotificationRouteInput = Pick<Notification, "type" | "entity_type" | "entity_id"> &
    Partial<Pick<Notification, "request_id">>

const TASK_FOCUS_BY_TYPE: Record<string, string> = {
    task_overdue: "overdue",
    task_due_soon: "tasks",
    task_assigned: "tasks",
}

const buildTasksHref = (params: { focus?: string; task?: string; approval?: string } = {}) => {
    const search = new URLSearchParams({ filter: "my_tasks" })
    if (params.focus) search.set("focus", params.focus)
    if (params.task) search.set("task", params.task)
    if (params.approval) search.set("approval", params.approval)
    return `/tasks?${search.toString()}`
}

function getRecordHref(notification: NotificationRouteInput): string | null {
    const { entity_type: entityType, entity_id: entityId } = notification
    if (!entityId) return null
    if (entityType === "surrogate" || entityType === "case") return `/surrogates/${entityId}`
    if (entityType === "intended_parent") return `/intended-parents/${entityId}`
    if (entityType === "match") return `/intended-parents/matches/${entityId}`
    if (entityType === "donor") return `/donors/${entityId}`
    if (entityType === "task" || entityType === "donor_task") return buildTasksHref({ task: entityId })
    if (entityType === "appointment") return `/appointments?appointment=${entityId}`
    return null
}

export function getNotificationHref(notification: NotificationRouteInput): string {
    const entityId = notification.entity_id ?? undefined

    switch (notification.type) {
        case "intelligent_suggestion_digest":
            return "/surrogates?dynamic_filter=intelligent_any"
        case "workflow_approval_requested":
            return buildTasksHref({ focus: "approvals", ...(entityId ? { approval: entityId } : {}) })
        case "workflow_approval_expired":
            return buildTasksHref({ focus: "approvals" })
        case "status_change_requested":
            // Pending: the approval row on /tasks. Resolved: the record itself.
            if (notification.request_id) {
                return buildTasksHref({ focus: "approvals", approval: notification.request_id })
            }
            return getRecordHref(notification) ?? buildTasksHref({ focus: "approvals" })
    }

    const taskFocus = TASK_FOCUS_BY_TYPE[notification.type]
    if (taskFocus) {
        return buildTasksHref({ focus: taskFocus, ...(entityId ? { task: entityId } : {}) })
    }

    return getRecordHref(notification) ?? "/notifications"
}
