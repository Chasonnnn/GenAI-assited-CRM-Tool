import { describe, expect, it } from "vitest"
import { formatSchedulingDate, formatSchedulingTime, localDateTimeToIso, schedulingDateKey } from "@/lib/scheduling-time"

describe("scheduling time display", () => {
    it("uses the selected zone for both date and time across midnight", () => {
        const instant = "2026-09-30T02:30:00Z"
        expect(schedulingDateKey(instant, "America/New_York")).toBe("2026-09-29")
        expect(schedulingDateKey(instant, "Asia/Tokyo")).toBe("2026-09-30")
        expect(formatSchedulingDate(instant, "America/Los_Angeles")).toContain("September 29")
        expect(formatSchedulingTime(instant, "America/Los_Angeles")).toBe("7:30 PM")
        expect(formatSchedulingTime(instant, "America/New_York")).toBe("10:30 PM")
    })

    it("rejects invalid normalized dates before an override is submitted", () => {
        expect(localDateTimeToIso("2026-02-30T09:00")).toBeNull()
        expect(localDateTimeToIso("2026-09-30T24:00")).toBeNull()
        expect(localDateTimeToIso("2026-09-30")).toBeNull()
        expect(localDateTimeToIso("")).toBeNull()
        expect(localDateTimeToIso("2026-09-30T09:30")).toBe(new Date("2026-09-30T09:30").toISOString())
    })
})
