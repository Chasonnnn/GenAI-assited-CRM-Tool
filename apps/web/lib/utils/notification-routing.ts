import type { Notification } from "@/lib/api/notifications"

type NotificationRouteInput = Pick<Notification, "type" | "entity_type" | "entity_id">

const APPROVAL_NOTIFICATION_TYPES = new Set([
    "workflow_approval_requested",
    "status_change_requested",
])

const TASK_FOCUS_BY_TYPE: Record<string, string> = {
    task_overdue: "overdue",
    task_due_soon: "tasks",
    task_assigned: "tasks",
}

const buildTasksHref = (focus?: string) => {
    const params = new URLSearchParams({ filter: "my_tasks" })
    if (focus) {
        params.set("focus", focus)
    }
    return `/tasks?${params.toString()}`
}

export function getNotificationHref(notification: NotificationRouteInput): string {
    if (APPROVAL_NOTIFICATION_TYPES.has(notification.type)) {
        return buildTasksHref("approvals")
    }

    const taskFocus = TASK_FOCUS_BY_TYPE[notification.type]
    if (taskFocus) {
        return buildTasksHref(taskFocus)
    }

    if (notification.entity_type === "surrogate" && notification.entity_id) {
        return `/surrogates/${notification.entity_id}`
    }
    if (notification.entity_type === "intended_parent" && notification.entity_id) {
        return `/intended-parents/${notification.entity_id}`
    }
    if (notification.entity_type === "task" && notification.entity_id) {
        return buildTasksHref()
    }
    if (notification.entity_type === "appointment" && notification.entity_id) {
        return "/appointments"
    }

    return "/notifications"
}
