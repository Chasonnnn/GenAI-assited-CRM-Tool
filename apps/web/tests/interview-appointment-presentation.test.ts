import { describe, expect, it } from "vitest"
import { appointmentBadgeStatus, localDateTimeToIso } from "@/components/surrogates/InterviewAppointmentManager"
import { stageBadgeStyle } from "@/lib/stage-colors"
import type { InterviewAppointment } from "@/lib/api/interview-appointment"

const appointment = (overrides: Partial<InterviewAppointment> = {}): InterviewAppointment => ({
    id: "appointment-1",
    scheduled_start: "2026-09-19T11:00:00.000Z",
    scheduled_end: "2026-09-19T12:00:00.000Z",
    client_timezone: "America/New_York",
    status: "scheduled",
    meeting_started_at: null,
    meeting_ended_at: null,
    ...overrides,
})

describe("interview appointment presentation", () => {
    it("derives actual cancellation, meeting, upcoming, and neutral past statuses", () => {
        expect(appointmentBadgeStatus(appointment({ status: "cancelled" }), new Date("2026-09-19T10:00:00Z"))).toBe("Cancelled")
        expect(appointmentBadgeStatus(appointment({ meeting_started_at: "2026-09-19T11:01:00Z" }), new Date("2026-09-19T11:15:00Z"))).toBe("Ongoing")
        expect(appointmentBadgeStatus(appointment(), new Date("2026-09-19T10:00:00Z"))).toBe("Upcoming")
        expect(appointmentBadgeStatus(appointment(), new Date("2026-09-19T12:00:00Z"))).toBe("Past")
    })

    it("uses the exact end boundary for Past", () => {
        expect(appointmentBadgeStatus(appointment(), new Date("2026-09-19T11:59:59.999Z"))).toBe("Ongoing")
        expect(appointmentBadgeStatus(appointment(), new Date("2026-09-19T12:00:00.000Z"))).toBe("Past")
    })

    it("converts a browser-local date-time to a timezone-aware ISO instant", () => {
        const result = localDateTimeToIso("2026-09-24T17:00")
        expect(result).toMatch(/^2026-09-2[45]T\d{2}:00:00\.000Z$/)
        expect(localDateTimeToIso("")).toBeNull()
    })

    it("keeps white text and colors that already reach AA contrast", () => {
        expect(stageBadgeStyle("#DB2777")).toEqual({ backgroundColor: "#DB2777", borderColor: "transparent", color: "#FFFFFF" })
        expect(stageBadgeStyle(" #64748b ")).toEqual({ backgroundColor: "#64748B", borderColor: "transparent", color: "#FFFFFF" })
    })

    it("passes through values that are not six-digit hex", () => {
        expect(stageBadgeStyle("").backgroundColor).toBe("")
        expect(stageBadgeStyle("#fff").backgroundColor).toBe("#fff")
        expect(stageBadgeStyle("var(--primary)").backgroundColor).toBe("var(--primary)")
    })

    // Every color seeded by apps/api/app/core/stage_definitions.py, plus the #6B7280 fallback.
    it.each([
        "#059669", "#06B6D4", "#0891B2", "#0D9488", "#0EA5E9", "#10B981", "#14B8A6", "#16A34A",
        "#22C55E", "#3B82F6", "#6366F1", "#64748B", "#6B7280", "#84CC16", "#8B5CF6", "#A855F7",
        "#B4536A", "#D97706", "#DB2777", "#EF4444", "#F59E0B", "#FDE68A",
    ])("gives seeded stage color %s white text at AA contrast", (color) => {
        const { backgroundColor, color: foreground } = stageBadgeStyle(color)
        expect(foreground).toBe("#FFFFFF")
        expect(contrastRatio(backgroundColor, "#FFFFFF")).toBeGreaterThanOrEqual(4.5)
        expect(luminance(backgroundColor)).toBeLessThanOrEqual(luminance(color))
        if (contrastRatio(color, "#FFFFFF") >= 4.5) expect(backgroundColor).toBe(color)
    })

    // Pairs that collapsed to one shade when every fill stopped exactly at 4.5:1.
    it.each([
        ["#10B981", "#059669"],
        ["#22C55E", "#16A34A"],
        ["#14B8A6", "#0D9488"],
        ["#06B6D4", "#0891B2"],
    ])("keeps the lighter stage color %s lighter than %s", (lighter, darker) => {
        const lighterFill = stageBadgeStyle(lighter).backgroundColor
        const darkerFill = stageBadgeStyle(darker).backgroundColor
        expect(luminance(lighterFill)).toBeGreaterThan(luminance(darkerFill) * 1.15)
    })
})

function luminance(hex: string): number {
    const channels = [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255)
    const [r, g, b] = channels.map((value) => value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}

function contrastRatio(first: string, second: string): number {
    const [high, low] = [luminance(first), luminance(second)].toSorted((a, b) => b - a)
    return (high! + 0.05) / (low! + 0.05)
}
