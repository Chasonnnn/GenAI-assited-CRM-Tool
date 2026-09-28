import { describe, expect, it } from "vitest"

import {
    getDonorSourceFilterLabel,
    getDonorSourceLabel,
    isDonorSource,
} from "@/lib/donor-source-labels"

describe("getDonorSourceLabel", () => {
    it.each([
        ["manual", "Manual"],
        ["meta", "Meta"],
        ["website", "Website"],
        ["tiktok", "TikTok"],
        ["Meta", "Unknown source"],
        ["shared_intake", "Unknown source"],
        ["toString", "Unknown source"],
        [null, "Unknown source"],
    ])("labels %j as %j", (value, label) => {
        expect(getDonorSourceLabel(value)).toBe(label)
    })
})

describe("getDonorSourceFilterLabel", () => {
    it.each([
        ["all", "All sources"],
        [null, "All sources"],
        ["referral", "Referral"],
        ["form_embed", "Unknown source"],
    ])("labels %j as %j", (value, label) => {
        expect(getDonorSourceFilterLabel(value)).toBe(label)
    })

    it("accepts only canonical source values", () => {
        expect(isDonorSource("meta")).toBe(true)
        expect(isDonorSource("Meta")).toBe(false)
        expect(isDonorSource("all")).toBe(false)
    })
})
