import { describe, expect, it } from "vitest"

import { getDonorSourceLabel } from "@/lib/donor-source-labels"

describe("getDonorSourceLabel", () => {
    it.each([
        ["manual", "Manual"],
        ["tiktok", "TikTok"],
        ["shared_intake", "Intake form"],
        ["manual_review_resolution", "Intake review"],
        ["shared_form_workflow", "Shared form workflow"],
        ["Spring Fair 2026!", "Other"],
        ["toString", "Other"],
    ])("labels %j as %j", (value, label) => {
        expect(getDonorSourceLabel(value)).toBe(label)
    })
})
