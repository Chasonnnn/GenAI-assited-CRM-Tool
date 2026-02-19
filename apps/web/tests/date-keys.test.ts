import { describe, expect, it } from "vitest"

import {
    formatDateKeyInTimeZone,
    formatPlainDateKey,
    isPastDateKey,
} from "@/lib/utils/date-keys"

describe("date key utilities", () => {
    it("formats plain date keys without timezone drift", () => {
        const localMidnight = new Date(2026, 0, 6)
        expect(formatPlainDateKey(localMidnight)).toBe("2026-01-06")
    })

    it("formats slot timestamps in a target timezone", () => {
        const slotStart = new Date("2026-01-06T17:00:00Z") // 9:00 AM PST
        expect(formatDateKeyInTimeZone(slotStart, "America/Los_Angeles")).toBe("2026-01-06")
    })

    it("compares date keys against 'today' in the selected timezone", () => {
        const now = new Date("2026-01-06T12:00:00Z") // Jan 6 in LA
        expect(isPastDateKey("2026-01-05", "America/Los_Angeles", now)).toBe(true)
        expect(isPastDateKey("2026-01-06", "America/Los_Angeles", now)).toBe(false)
        expect(isPastDateKey("2026-01-07", "America/Los_Angeles", now)).toBe(false)
    })
})
