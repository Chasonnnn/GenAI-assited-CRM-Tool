import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"

const mockMutate = vi.fn()
const mockUseUnifiedCalendarData = vi.fn()
const mockUseAppointment = vi.fn()
const mockUseRescheduleSlots = vi.fn()

const now = new Date()
const appointmentStartLocal = new Date(
    now.getFullYear(),
    now.getMonth(),
    10,
    12,
    0,
    0,
    0
)
const appointmentEndLocal = new Date(appointmentStartLocal.getTime() + 30 * 60 * 1000)
const rescheduleSlotStartLocal = new Date(
    now.getFullYear(),
    now.getMonth(),
    11,
    12,
    0,
    0,
    0
)
const rescheduleSlotEndLocal = new Date(rescheduleSlotStartLocal.getTime() + 30 * 60 * 1000)

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

        mockUseUnifiedCalendarData.mockReturnValue({
            appointments: [
                {
                    id: "appt-1",
                    appointment_type_name: "Initial Interview",
                    client_name: "Test Zhang",
                    client_email: "test@example.com",
                    client_phone: "+1-555-123-4567",
                    client_timezone: "America/Los_Angeles",
                    scheduled_start: appointmentStartLocal.toISOString(),
                    scheduled_end: appointmentEndLocal.toISOString(),
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
                scheduled_start: appointmentStartLocal.toISOString(),
                scheduled_end: appointmentEndLocal.toISOString(),
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
                        start: rescheduleSlotStartLocal.toISOString(),
                        end: rescheduleSlotEndLocal.toISOString(),
                    },
                ],
                appointment_type: null,
            },
            isLoading: false,
            isError: false,
        })
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

        const dateCells = screen.getAllByText(String(rescheduleSlotStartLocal.getDate()))
        const dropTarget = dateCells[0]?.closest("div")
        expect(dropTarget).toBeInTheDocument()
        fireEvent.drop(dropTarget as HTMLElement, { dataTransfer })

        expect(mockMutate).not.toHaveBeenCalled()
        expect(screen.getByText("Available Times")).toBeInTheDocument()
    })
})
