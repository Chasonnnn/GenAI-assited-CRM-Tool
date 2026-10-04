import { describe, expect, it } from "vitest"

import { canReviewFormSubmissions, canReviewRoutingSubmission } from "@/lib/forms/record-creation-access"

const v1 = (...permissions: string[]) => ({ policy_version: 1, permissions })
const v2 = (...permissions: string[]) => ({ policy_version: 2, permissions })

describe("canReviewFormSubmissions", () => {
    it("needs manage_forms under policy v1 and review_form_submissions under policy v2", () => {
        expect(canReviewFormSubmissions(v1("manage_forms"))).toBe(true)
        expect(canReviewFormSubmissions(v1("review_form_submissions"))).toBe(false)
        expect(canReviewFormSubmissions(v2("manage_forms", "view_form_submissions"))).toBe(false)
        expect(canReviewFormSubmissions(v2("review_form_submissions"))).toBe(true)
        expect(canReviewFormSubmissions(undefined)).toBe(false)
    })
})

describe("canReviewRoutingSubmission", () => {
    it("denies every routing action without the submission review permission", () => {
        const access = v2("manage_forms", "view_form_submissions", "edit_donors", "create_surrogates", "create_donors")
        expect(canReviewRoutingSubmission(access, "surrogate", "review")).toBe(false)
        expect(canReviewRoutingSubmission(access, "egg_donor", "create_lead")).toBe(false)
    })

    it("needs edit_donors on donor submissions", () => {
        expect(canReviewRoutingSubmission(v1("manage_forms"), "surrogate", "review")).toBe(true)
        expect(canReviewRoutingSubmission(v1("manage_forms"), "sperm_donor", "review")).toBe(false)
        expect(canReviewRoutingSubmission(v1("manage_forms", "edit_donors"), "sperm_donor", "create_lead")).toBe(true)
    })

    it("needs create permission to create the lead under policy v2", () => {
        expect(canReviewRoutingSubmission(v2("review_form_submissions"), "surrogate", "review")).toBe(true)
        expect(canReviewRoutingSubmission(v2("review_form_submissions"), "surrogate", "create_lead")).toBe(false)
        expect(canReviewRoutingSubmission(v2("review_form_submissions", "create_surrogates"), "surrogate", "create_lead")).toBe(true)
        expect(canReviewRoutingSubmission(v2("review_form_submissions", "edit_donors", "create_surrogates"), "egg_donor", "create_lead")).toBe(false)
    })
})
