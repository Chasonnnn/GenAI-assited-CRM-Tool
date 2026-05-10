import { describe, expect, it } from "vitest"

import { formatDate, formatDateTime, formatRace } from "@/lib/formatters"

describe("formatters", () => {
    it("formats dates with cached custom options", () => {
        const value = "2026-05-09T12:00:00.000Z"

        expect(formatDate(value, { dateStyle: "long", timeZone: "UTC" })).toBe("May 9, 2026")
        expect(formatDate(value, { timeZone: "UTC", dateStyle: "long" })).toBe("May 9, 2026")
    })

    it("formats fallback values for invalid dates", () => {
        expect(formatDate("not-a-date", undefined, "Unknown")).toBe("Unknown")
        expect(formatDateTime(null, "Never")).toBe("Never")
    })

    it("normalizes race labels", () => {
        expect(formatRace("black_or_african_american")).toBe("Black or African American")
        expect(formatRace("not-provided")).toBe("Not Provided")
    })
})
