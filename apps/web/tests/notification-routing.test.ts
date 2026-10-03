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

        expect(href).toBe("/tasks?filter=my_tasks&task=task-2")
    })

    it("routes donor notifications to donor detail", () => {
        const href = getNotificationHref({
            type: "workflow_notification",
            entity_type: "donor",
            entity_id: "donor-1",
        })

        expect(href).toBe("/donors/donor-1")
    })

    it("routes intelligent suggestion digests to dynamic surrogate filter", () => {
        const href = getNotificationHref({
            type: "intelligent_suggestion_digest",
            entity_type: null,
            entity_id: null,
        })

        expect(href).toBe("/surrogates?dynamic_filter=intelligent_any")
    })
})

describe("match notifications", () => {
    it("routes match conflict notifications to the match detail", () => {
        expect(getNotificationHref({ type: "match_conflict", entity_type: "match", entity_id: "match-1" })).toBe("/intended-parents/matches/match-1")
    })

    it("routes match cancellation decisions to the match detail", () => {
        expect(getNotificationHref({ type: "status_change_approved", entity_type: "match", entity_id: "match-2" })).toBe("/intended-parents/matches/match-2")
    })

    it("points pending match cancellation approvals at their approval row", () => {
        expect(getNotificationHref({ type: "status_change_requested", entity_type: "match", entity_id: "match-3", request_id: "req-3" })).toBe("/tasks?filter=my_tasks&focus=approvals&approval=req-3")
    })

    it("opens the match once its cancellation request is no longer pending", () => {
        expect(getNotificationHref({ type: "status_change_requested", entity_type: "match", entity_id: "match-3", request_id: null })).toBe("/intended-parents/matches/match-3")
    })
})

describe("record deep links", () => {
    it("points workflow approvals at their approval row", () => {
        expect(getNotificationHref({ type: "workflow_approval_requested", entity_type: "task", entity_id: "task-9" })).toBe("/tasks?filter=my_tasks&focus=approvals&approval=task-9")
    })

    it("opens the assigned or overdue task", () => {
        expect(getNotificationHref({ type: "task_assigned", entity_type: "task", entity_id: "task-4" })).toBe("/tasks?filter=my_tasks&focus=tasks&task=task-4")
        expect(getNotificationHref({ type: "task_overdue", entity_type: "donor_task", entity_id: "task-5" })).toBe("/tasks?filter=my_tasks&focus=overdue&task=task-5")
    })

    it("opens the requested appointment", () => {
        expect(getNotificationHref({ type: "appointment_requested", entity_type: "appointment", entity_id: "appt-1" })).toBe("/appointments?appointment=appt-1")
    })
})
