import { describe, expect, it } from "vitest"
import type { FormSubmissionRead } from "@/lib/api/forms"
import { readAnswerValue } from "@/lib/forms/submission-presentation"

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
