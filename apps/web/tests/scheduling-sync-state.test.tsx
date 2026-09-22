import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { SchedulingSyncBadge, SchedulingSyncState } from "@/components/appointments/SchedulingSyncState"

const retry = vi.fn()
const resolve = vi.fn()

vi.mock("@/components/app-link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}))

vi.mock("@/lib/hooks/use-appointments", () => ({
    useRetryAppointmentGoogleSync: () => ({ mutate: retry, isPending: false }),
    useResolveAppointmentGoogleConflict: () => ({ mutate: resolve, isPending: false }),
}))

const base = {
    id: "appointment-1",
    scheduling: {
        revision: 4,
        capabilities: {
            can_reschedule: false,
            can_cancel: false,
            can_retry_google_sync: false,
            can_resolve_google_conflict: false,
        },
        google_sync: { state: "failed" as const, linked: true, error_code: "provider_unavailable", conflict: null },
    },
}

describe("SchedulingSyncState", () => {
    it("does not expose provider actions without server capability", () => {
        render(<SchedulingSyncState appointment={base} />)
        expect(screen.getByRole("alert")).toHaveTextContent("Google Calendar update failed.")
        expect(screen.queryByRole("button", { name: /retry google update/i })).not.toBeInTheDocument()
    })

    it("sends revision and request id only when the server permits retry", () => {
        const appointment = {
            ...base,
            scheduling: { ...base.scheduling, capabilities: { ...base.scheduling.capabilities, can_retry_google_sync: true } },
        }
        render(<SchedulingSyncState appointment={appointment} />)
        fireEvent.click(screen.getByRole("button", { name: /retry google update/i }))
        expect(retry).toHaveBeenCalledWith(expect.objectContaining({ appointmentId: "appointment-1", expectedRevision: 4, requestId: expect.any(String) }), expect.anything())
    })

    it("offers the same recovery action for an unlinked appointment only when permitted", () => {
        const appointment = {
            ...base,
            scheduling: { ...base.scheduling, capabilities: { ...base.scheduling.capabilities, can_retry_google_sync: true }, google_sync: { state: "unlinked" as const, linked: false, error_code: "booking_destination_missing", conflict: null } },
        }
        render(<SchedulingSyncState appointment={appointment} />)
        expect(screen.getByText("Google Calendar needs setup.")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Calendar settings" })).toHaveAttribute("href", "/settings/integrations")
        fireEvent.click(screen.getByRole("button", { name: /retry google update/i }))
        expect(retry).toHaveBeenCalledWith(expect.objectContaining({ appointmentId: "appointment-1", expectedRevision: 4 }), expect.anything())
    })

    it("uses an amber badge for conflicts and red for failures", () => {
        const { rerender } = render(<SchedulingSyncBadge scheduling={{ ...base.scheduling, google_sync: { state: "conflict", linked: true, error_code: null, conflict: null } }} />)
        expect(screen.getByText("Google conflict")).toHaveClass("text-amber-800")
        rerender(<SchedulingSyncBadge scheduling={base.scheduling} />)
        expect(screen.getByText("Google update failed")).toHaveClass("text-destructive")
    })

    it("keeps a conflict read-only when resolution capability is absent", () => {
        render(<SchedulingSyncState appointment={{ ...base, scheduling: { ...base.scheduling, google_sync: { state: "conflict", linked: true, error_code: null, conflict: null } } }} />)
        expect(screen.getByText("Manual review required")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /keep crm schedule|use google schedule/i })).not.toBeInTheDocument()
    })

    it("renders cancellation state from conflict snapshots", () => {
        const appointment = {
            ...base,
            scheduling: {
                ...base.scheduling,
                google_sync: { state: "conflict" as const, linked: true, error_code: null, conflict: { local: { status: "cancelled" }, remote: null } },
            },
        }
        render(<SchedulingSyncState appointment={appointment} />)
        expect(screen.getByText("Cancelled")).toBeInTheDocument()
        expect(screen.getByText("Google event is unavailable")).toBeInTheDocument()
    })

    it("does not resolve a conflict until a selected schedule is applied", () => {
        const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined)
        const appointment = {
            ...base,
            scheduling: {
                ...base.scheduling,
                capabilities: { ...base.scheduling.capabilities, can_resolve_google_conflict: true },
                google_sync: { state: "conflict" as const, linked: true, error_code: null, conflict: { etag: "event-v1", local: { start: "2026-09-30T11:00:00Z", end: "2026-09-30T11:30:00Z" }, remote: { start: "2026-09-30T12:00:00Z", end: "2026-09-30T12:30:00Z" } } },
            },
        }
        const { rerender } = render(<SchedulingSyncState appointment={appointment} />)
        const apply = screen.getByRole("button", { name: /apply selected schedule/i })
        expect(apply).toBeDisabled()
        fireEvent.click(screen.getByRole("radio", { name: /^Google Calendar/ }))
        expect(consoleError).not.toHaveBeenCalled()
        expect(resolve).not.toHaveBeenCalled()
        fireEvent.click(apply)
        expect(resolve).toHaveBeenCalledWith(expect.objectContaining({ appointmentId: "appointment-1", expectedRevision: 4, expectedEtag: "event-v1", resolution: "google" }), expect.anything())

        rerender(<SchedulingSyncState appointment={{ ...appointment, scheduling: { ...appointment.scheduling, revision: 5, google_sync: { ...appointment.scheduling.google_sync, conflict: { ...appointment.scheduling.google_sync.conflict, etag: "event-v2" } } } }} />)
        expect(screen.getByRole("button", { name: /apply selected schedule/i })).toBeDisabled()
        consoleError.mockRestore()
    })
})
