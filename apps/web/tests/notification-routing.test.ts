import { describe, expect, it } from "vitest"

import { getNotificationHref } from "@/lib/utils/notification-routing"

describe("getNotificationHref", () => {
    it("routes workflow approval expiry notifications to approvals", () => {
        const href = getNotificationHref({
            type: "workflow_approval_expired",
            entity_type: "task",
            entity_id: "task-1",
        })

        expect(href).toBe("/tasks?filter=my_tasks&focus=approvals")
    })

    it("routes legacy case entity notifications to surrogate detail", () => {
        const href = getNotificationHref({
            type: "interview_transcription_completed",
            entity_type: "case",
            entity_id: "surrogate-1",
        })

        expect(href).toBe("/surrogates/surrogate-1")
    })

    it("routes workflow notifications by their task entity", () => {
        const href = getNotificationHref({
            type: "workflow_notification",
            entity_type: "task",
            entity_id: "task-2",
        })

        expect(href).toBe("/tasks?filter=my_tasks")
    })
})
