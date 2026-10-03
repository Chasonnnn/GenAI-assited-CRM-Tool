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

    it("routes donor notifications to donor detail", () => {
        const href = getNotificationHref({
            type: "workflow_notification",
            entity_type: "donor",
            entity_id: "donor-1",
        })

        expect(href).toBe("/donors/donor-1")
    })

    it("routes routing review notifications to Form Submissions on their form", () => {
        expect(getNotificationHref({
            type: "form_submission_routing_review",
            entity_type: "form",
            entity_id: "form-1",
        })).toBe("/automation/form-submissions?form=form-1")
        expect(getNotificationHref({
            type: "form_submission_routing_review",
            entity_type: "form",
            entity_id: null,
        })).toBe("/notifications")
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

    it("keeps pending match cancellation approvals in the approvals queue", () => {
        expect(getNotificationHref({ type: "status_change_requested", entity_type: "match", entity_id: "match-3" })).toBe("/tasks?filter=my_tasks&focus=approvals")
    })
})
