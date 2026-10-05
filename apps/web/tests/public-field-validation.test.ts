import { readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

import type { FormField } from "@/lib/api/forms"
import { getPublicFieldValidationError } from "@/lib/forms/public-field-validation"

type EmailRuleCase = { name: string; address: string }
type EmailRuleGroup = "accepted" | "rejected" | "rejected_by_api_only" | "rejected_by_browser_only"

// The API suite checks the same file in apps/api/tests/test_form_submission_service.py, so the
// public forms and the API keep one verdict for each address.
const cases = JSON.parse(
    readFileSync(join(process.cwd(), "../api/tests/fixtures/public_email_rule_cases.json"), "utf8"),
) as Record<EmailRuleGroup, EmailRuleCase[]>

const EMAIL_FIELD: FormField = { key: "email", label: "Email", type: "email", required: true }
const INVALID_EMAIL = "Email must be a valid email address."

const getEmailError = (address: string) => getPublicFieldValidationError(EMAIL_FIELD, address)

describe("public email field validation", () => {
    it.each(cases.accepted)("accepts $name", ({ address }) => {
        expect(getEmailError(address)).toBeNull()
    })

    it.each(cases.rejected)("rejects $name", ({ address }) => {
        expect(getEmailError(address)).toBe(INVALID_EMAIL)
    })

    // A browser has no IDNA tables, so the API alone rejects these internationalized domain names.
    it.each(cases.rejected_by_api_only)("leaves $name to the API", ({ address }) => {
        expect(getEmailError(address)).toBeNull()
    })

    // The API accepts these through pydantic's "Name <address>" form and stores them unchanged.
    it.each(cases.rejected_by_browser_only)("rejects $name", ({ address }) => {
        expect(getEmailError(address)).toBe(INVALID_EMAIL)
    })
})
