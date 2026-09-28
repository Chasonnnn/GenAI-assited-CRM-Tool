import { describe, expect, it } from "vitest"
import { appointmentBadgeStatus, localDateTimeToIso } from "@/components/surrogates/InterviewAppointmentManager"
import { readableForeground } from "@/lib/stage-colors"
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

    it("uses a readable dark foreground for rollout yellow and white for purple", () => {
        expect(readableForeground("#FDE68A")).toBe("#422006")
        expect(readableForeground("#A855F7")).toBe("#FFFFFF")
    })

    it("uses dark text on mid-luminance stage colors", () => {
        expect(readableForeground("#06b6d4")).toBe("#422006")
        expect(readableForeground("#10b981")).toBe("#422006")
        expect(readableForeground(" #06B6D4 ")).toBe("#422006")
    })

    it("falls back to white for values that are not six-digit hex", () => {
        expect(readableForeground("")).toBe("#FFFFFF")
        expect(readableForeground("#fff")).toBe("#FFFFFF")
        expect(readableForeground("var(--primary)")).toBe("#FFFFFF")
    })

    // Every color seeded by apps/api/app/core/stage_definitions.py, plus the #6B7280 fallback.
    it.each([
        ["#059669", "#422006"],
        ["#06B6D4", "#422006"],
        ["#0891B2", "#422006"],
        ["#0D9488", "#422006"],
        ["#0EA5E9", "#422006"],
        ["#10B981", "#422006"],
        ["#14B8A6", "#422006"],
        ["#16A34A", "#422006"],
        ["#22C55E", "#422006"],
        ["#3B82F6", "#422006"],
        ["#6366F1", "#FFFFFF"],
        ["#64748B", "#FFFFFF"],
        ["#6B7280", "#FFFFFF"],
        ["#84CC16", "#422006"],
        ["#8B5CF6", "#FFFFFF"],
        ["#A855F7", "#FFFFFF"],
        ["#B4536A", "#FFFFFF"],
        ["#D97706", "#422006"],
        ["#DB2777", "#FFFFFF"],
        ["#EF4444", "#422006"],
        ["#F59E0B", "#422006"],
        ["#FDE68A", "#422006"],
    ])("picks the higher-contrast foreground for seeded stage color %s", (background, expected) => {
        const foreground = readableForeground(background)
        const other = foreground === "#FFFFFF" ? "#422006" : "#FFFFFF"
        expect(foreground).toBe(expected)
        expect(contrastRatio(background, foreground)).toBeGreaterThan(contrastRatio(background, other))
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
