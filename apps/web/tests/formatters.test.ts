import { afterAll, describe, expect, it, vi } from "vitest"

import { formatDate, formatDateTime, formatRace, formatRelativeTime } from "@/lib/formatters"

// A US zone, set before the formatters module builds its Intl formatters, so a date-only value
// read as UTC midnight would show the previous day.
const originalTimeZone = vi.hoisted(() => {
    const original = process.env.TZ
    process.env.TZ = "America/New_York"
    return original
})
afterAll(() => {
    if (originalTimeZone === undefined) delete process.env.TZ
    else process.env.TZ = originalTimeZone
})

describe("formatters", () => {
    it("formats a date-only value as that calendar day in a US time zone", () => {
        expect(formatDate("2026-10-09")).toBe("Oct 9, 2026")
        expect(formatDate("2026-01-01", { month: "long", day: "numeric", year: "numeric" })).toBe("January 1, 2026")
        expect(formatDateTime("2026-10-09")).toMatch(/^Oct 9, 2026 at 12:00\sAM$/)
        // Timestamps keep their instant: 02:00 UTC is still the previous evening in New York.
        expect(formatDate("2026-10-09T02:00:00Z")).toBe("Oct 8, 2026")
    })

    it("measures relative time from local midnight of a date-only value", () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date(2026, 9, 9, 12))
        try {
            expect(formatRelativeTime("2026-10-09")).toBe("12 hours ago")
        } finally {
            vi.useRealTimers()
        }
    })

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
