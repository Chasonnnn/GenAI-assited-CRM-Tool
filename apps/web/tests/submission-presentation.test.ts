import { describe, expect, it } from "vitest"
import type { FormSubmissionRead } from "@/lib/api/forms"
import {
    matchReasonLabel,
    readAnswerValue,
    submissionOutcomeLabel,
    submissionStatusBadgeClass,
    submissionStatusLabel,
} from "@/lib/forms/submission-presentation"

function submission(answers: FormSubmissionRead["answers"]) {
    return { id: "submission-1", answers } as FormSubmissionRead
}

describe("readAnswerValue", () => {
    it("reads donor identity from mapped field keys before raw keys", () => {
        const record = submission({ donor_legal_name: "  Dana Example  ", full_name: "Raw Name", contact: "dana@example.test" })
        const mappings = [
            { field_key: "donor_legal_name", surrogate_field: "full_name" },
            { field_key: "contact", surrogate_field: "email" },
        ]

        expect(readAnswerValue(record, ["full_name", "name"], mappings)).toBe("Dana Example")
        expect(readAnswerValue(record, ["email", "email_address"], mappings)).toBe("dana@example.test")
    })

    it("falls back to raw keys when the mapped answer is blank or mappings are absent", () => {
        const record = submission({ donor_legal_name: "   ", name: " Sam Sample " })
        const mappings = [{ field_key: "donor_legal_name", surrogate_field: "full_name" }]

        expect(readAnswerValue(record, ["full_name", "name"], mappings)).toBe("Sam Sample")
        expect(readAnswerValue(record, ["full_name", "name"])).toBe("Sam Sample")
    })

    it("returns a placeholder for blank, missing, and non-text answers", () => {
        const record = submission({ full_name: "  ", phone: 5550100, email: null })

        expect(readAnswerValue(record, ["full_name", "name"])).toBe("—")
        expect(readAnswerValue(record, ["phone"])).toBe("—")
        expect(readAnswerValue(record, ["email", "email_address"], [])).toBe("—")
    })
})

describe("matchReasonLabel", () => {
    it.each([
        ["donor_email_name_type_exact", "Name, email and donor type match"],
        ["donor_identity_conflict", "Email or phone belongs to a different donor"],
        ["donor_photo_requires_review", "Profile photo needs review"],
        ["existing_submission_for_donor", "Donor already has an application on this form"],
        ["donor_email_phone_match", "Email and phone match"],
        ["manually_linked", "Linked by reviewer"],
        ["phone_dob_name_ambiguous", "Several records share name, date of birth and phone"],
        ["workflow_pending", "Waiting for routing"],
        ["routing_review_dismissed", "Routing review dismissed"],
    ])("labels %s", (reason, label) => {
        expect(matchReasonLabel(reason)).toBe(label)
    })

    it("never shows a raw or missing reason code", () => {
        expect(matchReasonLabel("future_reason_code")).toBe("Other reason")
        expect(matchReasonLabel(null)).toBe("—")
        expect(matchReasonLabel(undefined)).toBe("—")
    })
})

describe("submissionStatusLabel", () => {
    it.each([
        ["pending_review", "Pending Review", "text-stone-700"],
        ["approved", "Approved", "text-emerald-700"],
        ["rejected", "Rejected", "text-red-700"],
    ] as const)("labels and colors %s", (status, label, color) => {
        expect(submissionStatusLabel(status)).toBe(label)
        expect(submissionStatusBadgeClass(status)).toContain(color)
    })
})

describe("submissionOutcomeLabel", () => {
    it.each([
        ["linked", "Matched"],
        ["lead_created", "Lead Created"],
        ["routing_review", "Routing Review"],
        ["ambiguous_review", "Pending Match"],
        ["workflow_pending", "Pending Match"],
    ] as const)("labels %s", (matchStatus, label) => {
        expect(submissionOutcomeLabel({ match_status: matchStatus } as FormSubmissionRead)).toBe(label)
    })
})
