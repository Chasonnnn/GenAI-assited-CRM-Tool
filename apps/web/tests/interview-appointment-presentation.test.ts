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
})
