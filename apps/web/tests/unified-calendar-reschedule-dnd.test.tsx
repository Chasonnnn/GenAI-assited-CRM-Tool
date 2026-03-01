import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"

const mockMutate = vi.fn()
const mockUseUnifiedCalendarData = vi.fn()
const mockUseAppointment = vi.fn()
const mockUseRescheduleSlots = vi.fn()

vi.mock("@/lib/hooks/use-unified-calendar-data", () => ({
    useUnifiedCalendarData: (args: unknown) => mockUseUnifiedCalendarData(args),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSurrogates: () => ({ data: { items: [] } }),
}))

vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParents: () => ({ data: { items: [] } }),
}))

vi.mock("@/lib/hooks/use-appointments", () => ({
    useRescheduleAppointment: () => ({
        mutate: mockMutate,
        isPending: false,
    }),
    useUpdateAppointmentLink: () => ({
        mutate: vi.fn(),
        isPending: false,
    }),
    useAppointment: (appointmentId: string) => mockUseAppointment(appointmentId),
    useApproveAppointment: () => ({
        mutate: vi.fn(),
        isPending: false,
    }),
    useCancelAppointment: () => ({
        mutate: vi.fn(),
        isPending: false,
    }),
    useRescheduleSlots: (
        appointmentId: string,
        dateStart: string,
        dateEnd?: string,
        clientTimezone?: string,
        enabled = true,
    ) => mockUseRescheduleSlots(appointmentId, dateStart, dateEnd, clientTimezone, enabled),
}))

describe("UnifiedCalendar drag-to-reschedule", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.useFakeTimers({ toFake: ['Date'] })
        vi.setSystemTime(new Date("2026-02-24T12:00:00Z"))

        mockUseUnifiedCalendarData.mockReturnValue({
            appointments: [
                {
                    id: "appt-1",
                    appointment_type_name: "Initial Interview",
                    client_name: "Test Zhang",
                    client_email: "test@example.com",
                    client_phone: "+1-555-123-4567",
                    client_timezone: "America/Los_Angeles",
                    scheduled_start: "2026-02-25T22:30:00Z",
                    scheduled_end: "2026-02-25T23:00:00Z",
                    duration_minutes: 30,
                    meeting_mode: "zoom",
                    meeting_location: null,
                    dial_in_number: null,
                    status: "confirmed",
                    zoom_join_url: null,
                    google_meet_url: null,
                    surrogate_id: null,
                    surrogate_number: null,
                    intended_parent_id: null,
                    intended_parent_name: null,
                    created_at: "2026-02-20T00:00:00Z",
                },
            ],
            appointmentsLoading: false,
            tasks: [],
            tasksLoading: false,
            googleEvents: [],
            calendarConnected: true,
            calendarError: null,
        })

        mockUseAppointment.mockReturnValue({
            data: {
                id: "appt-1",
                appointment_type_name: "Initial Interview",
                client_name: "Test Zhang",
                client_email: "test@example.com",
                client_phone: "+1-555-123-4567",
                client_timezone: "America/Los_Angeles",
                client_notes: null,
                scheduled_start: "2026-02-25T22:30:00Z",
                scheduled_end: "2026-02-25T23:00:00Z",
                duration_minutes: 30,
                meeting_mode: "zoom",
                meeting_location: null,
                dial_in_number: null,
                status: "confirmed",
                pending_expires_at: null,
                zoom_join_url: null,
                google_meet_url: null,
            },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })

        mockUseRescheduleSlots.mockReturnValue({
            data: {
                slots: [
                    {
                        start: "2026-02-26T18:00:00Z",
                        end: "2026-02-26T18:30:00Z",
                    },
                ],
                appointment_type: null,
            },
            isLoading: false,
            isError: false,
        })
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("opens reschedule selection flow on drop instead of rescheduling immediately", () => {
        render(<UnifiedCalendar />)

        const draggableAppt = screen.getByText(/Test Zhang/i).closest('[draggable="true"]') as HTMLElement
        expect(draggableAppt).toBeInTheDocument()

        const dataTransfer = {
            effectAllowed: "",
            setData: vi.fn(),
        }
        fireEvent.dragStart(draggableAppt, { dataTransfer })

        const dateCells = screen.getAllByText("26")
        const dropTarget = dateCells[0]?.closest("div")
        expect(dropTarget).toBeInTheDocument()
        fireEvent.drop(dropTarget as HTMLElement, { dataTransfer })

        expect(mockMutate).not.toHaveBeenCalled()
        expect(screen.getByText("Available Times")).toBeInTheDocument()
    })
})
