import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, within } from "@testing-library/react"
import "@testing-library/jest-dom"
import { UnifiedCalendar } from "@/components/appointments/UnifiedCalendar"
import { getAppointmentStatusTone } from "@/lib/appointment-status-tones"
import { format } from "date-fns"

const mockMutate = vi.fn()
const mockUseUnifiedCalendarData = vi.fn()
const mockUseAppointment = vi.fn()
const mockUseRescheduleSlots = vi.fn()
const mockUseIntendedParents = vi.fn()
const mockUseEffectivePermissions = vi.fn()

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
    useIntendedParents: (filters: unknown, options: unknown) =>
        mockUseIntendedParents(filters, options),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: {
            user_id: "user-1",
            role: "case_manager",
        },
    }),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: (userId: string | null) => mockUseEffectivePermissions(userId),
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
        mockUseIntendedParents.mockReturnValue({ data: { items: [] } })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_intended_parents"] },
            isLoading: false,
        })

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

    it("does not fetch intended parents before appointment link editing starts", () => {
        render(<UnifiedCalendar />)

        fireEvent.click(screen.getByRole("button", { name: /Test Zhang/i }))
        expect(mockUseIntendedParents).toHaveBeenCalledWith(
            { per_page: 100 },
            { enabled: false }
        )
        expect(mockUseIntendedParents).not.toHaveBeenCalledWith(
            { per_page: 100 },
            { enabled: true }
        )

        fireEvent.click(screen.getByRole("button", { name: "Link" }))
        expect(mockUseIntendedParents).toHaveBeenLastCalledWith(
            { per_page: 100 },
            { enabled: true }
        )
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
        expect(screen.getByRole("group", { name: "Available times" })).toBeInTheDocument()
    })

    it("gives the period navigation a full row below sm so the title is not cut off", () => {
        render(<UnifiedCalendar />)

        const nav = screen.getByTestId("calendar-period-nav")
        expect(nav).toHaveClass("w-full", "sm:w-auto")
        expect(within(nav).getByRole("button", { name: "Previous period" })).toBeInTheDocument()
        expect(within(nav).queryByRole("button", { name: "Today" })).not.toBeInTheDocument()
        // Today and the period switcher share the second row.
        expect(screen.getByRole("combobox", { name: "Calendar period" })).toHaveClass("flex-1", "sm:w-36")
    })

    it("renders calendar appointments as native draggable buttons", () => {
        render(<UnifiedCalendar />)

        const appointmentButton = screen.getByRole("button", { name: /Test Zhang/i })
        expect(appointmentButton.tagName).toBe("BUTTON")
        expect(appointmentButton).toHaveAttribute("type", "button")
        expect(appointmentButton).toHaveAttribute("draggable", "true")
    })

    it("renders appointment chips with the status tint instead of white text on a solid fill", () => {
        render(<UnifiedCalendar />)

        const appointmentButton = screen.getByRole("button", { name: /Test Zhang/i })
        expect(appointmentButton).toHaveClass(...getAppointmentStatusTone("confirmed").tint.split(" "))
        expect(appointmentButton).not.toHaveClass("text-white", "bg-green-500")
        expect(screen.getByText("Confirmed").previousElementSibling).toHaveClass(getAppointmentStatusTone("confirmed").dot)
    })

    it("renders Google Calendar events as native links", () => {
        const googleEventStart = new Date(
            now.getFullYear(),
            now.getMonth(),
            12,
            10,
            0,
            0,
            0
        )
        const googleEventEnd = new Date(googleEventStart.getTime() + 30 * 60 * 1000)
        mockUseUnifiedCalendarData.mockReturnValue({
            appointments: [],
            appointmentsLoading: false,
            tasks: [],
            tasksLoading: false,
            googleEvents: [
                {
                    id: "gcal-1",
                    summary: "Partner sync",
                    start: googleEventStart.toISOString(),
                    end: googleEventEnd.toISOString(),
                    html_link: "https://calendar.google.com/event?eid=gcal-1",
                    is_all_day: false,
                    source: "google",
                },
            ],
            calendarConnected: true,
            calendarError: null,
        })

        render(<UnifiedCalendar />)

        const eventLink = screen.getByRole("link", { name: /partner sync/i })
        expect(eventLink).toHaveAttribute("href", "https://calendar.google.com/event?eid=gcal-1")
        expect(eventLink).toHaveAttribute("target", "_blank")
        expect(eventLink).toHaveAttribute("rel", "noopener noreferrer")
    })

    it("labels linked appointment unlink actions with the linked record names", () => {
        mockUseUnifiedCalendarData.mockReturnValue({
            appointments: [
                {
                    id: "appt-linked",
                    appointment_type_name: "Initial Interview",
                    client_name: "Linked Appointment",
                    client_email: "linked@example.com",
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
                    surrogate_id: "surrogate-1",
                    surrogate_number: "S10001",
                    intended_parent_id: "ip-1",
                    intended_parent_name: "Casey Parent",
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

        // The detail dialog reads links from the appointment detail, not the calendar list item.
        mockUseAppointment.mockReturnValue({
            data: {
                id: "appt-linked",
                appointment_type_name: "Initial Interview",
                client_name: "Linked Appointment",
                client_email: "linked@example.com",
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
                surrogate_id: "surrogate-1",
                surrogate_number: "S10001",
                intended_parent_id: "ip-1",
                intended_parent_name: "Casey Parent",
            },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })

        render(<UnifiedCalendar includeGoogleEvents={false} />)

        fireEvent.click(screen.getByText(/Linked Appointment/i))

        expect(
            screen.getByRole("button", { name: /unlink surrogate s10001/i })
        ).toBeInTheDocument()
        expect(
            screen.getByRole("button", { name: /unlink intended parent casey parent/i })
        ).toBeInTheDocument()
    })

    it("keeps all month-view items accessible from the overflow action", () => {
        const overflowDay = new Date(now.getFullYear(), now.getMonth(), 15, 9, 0, 0, 0)
        const overflowDate = format(overflowDay, "yyyy-MM-dd")

        mockUseUnifiedCalendarData.mockReturnValue({
            appointments: [
                {
                    id: "appt-overflow-1",
                    appointment_type_name: "Initial Interview",
                    client_name: "Appointment 1",
                    client_email: "appt1@example.com",
                    client_phone: null,
                    client_timezone: "America/Los_Angeles",
                    scheduled_start: new Date(now.getFullYear(), now.getMonth(), 15, 9, 0, 0, 0).toISOString(),
                    scheduled_end: new Date(now.getFullYear(), now.getMonth(), 15, 9, 30, 0, 0).toISOString(),
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
                {
                    id: "appt-overflow-2",
                    appointment_type_name: "Follow-up",
                    client_name: "Appointment 2",
                    client_email: "appt2@example.com",
                    client_phone: null,
                    client_timezone: "America/Los_Angeles",
                    scheduled_start: new Date(now.getFullYear(), now.getMonth(), 15, 10, 0, 0, 0).toISOString(),
                    scheduled_end: new Date(now.getFullYear(), now.getMonth(), 15, 10, 30, 0, 0).toISOString(),
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
            tasks: Array.from({ length: 5 }, (_, index) => ({
                id: `task-overflow-${index + 1}`,
                title: `Task ${index + 1}`,
                description: null,
                task_type: "other",
                surrogate_id: null,
                surrogate_number: null,
                owner_type: "user",
                owner_id: "u1",
                owner_name: "Owner",
                created_by_user_id: "u1",
                created_by_name: "Owner",
                due_date: overflowDate,
                due_time: `${String(11 + index).padStart(2, "0")}:00:00`,
                duration_minutes: null,
                is_completed: false,
                completed_at: null,
                completed_by_name: null,
                created_at: "2026-02-20T00:00:00Z",
            })),
            tasksLoading: false,
            googleEvents: [],
            calendarConnected: true,
            calendarError: null,
        })

        render(<UnifiedCalendar includeGoogleEvents={false} />)

        expect(screen.queryByText("Task 5")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "+4 more items" }))

        expect(
            screen.getByRole("heading", { name: format(overflowDay, "EEEE, MMMM d") })
        ).toBeInTheDocument()
        expect(screen.getByText("Task 5")).toBeInTheDocument()
        expect(screen.getByText("Appointment 2")).toBeInTheDocument()
    })

    it("orders same-day month-cell tasks by due time and shows no count badge", () => {
        const dueDate = format(new Date(now.getFullYear(), now.getMonth(), 20), "yyyy-MM-dd")
        // Listed in creation order; untimed first, as the API used to return them.
        const tasks = [
            { id: "t-untimed", title: "Delta", due_time: null },
            { id: "t-3pm", title: "Alpha", due_time: "15:00:00" },
            { id: "t-11am", title: "Bravo", due_time: "11:00:00" },
            { id: "t-9am", title: "Charlie", due_time: "09:00:00" },
        ].map((task) => ({
            ...task,
            description: null,
            task_type: "other",
            surrogate_id: null,
            surrogate_number: null,
            owner_type: "user",
            owner_id: "u1",
            owner_name: "Owner",
            created_by_user_id: "u1",
            created_by_name: "Owner",
            due_date: dueDate,
            duration_minutes: null,
            is_completed: false,
            completed_at: null,
            completed_by_name: null,
            created_at: "2026-02-20T00:00:00Z",
        }))
        mockUseUnifiedCalendarData.mockReturnValue({
            appointments: [],
            appointmentsLoading: false,
            tasks,
            tasksLoading: false,
            googleEvents: [],
            calendarConnected: true,
            calendarError: null,
        })

        render(<UnifiedCalendar includeGoogleEvents={false} />)

        const charlie = screen.getByText(/Charlie$/)
        const bravo = screen.getByText(/Bravo$/)
        const alpha = screen.getByText(/Alpha$/)
        expect(charlie.compareDocumentPosition(bravo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
        expect(bravo.compareDocumentPosition(alpha) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
        expect(screen.queryByText(/Delta$/)).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "+1 more items" })).toBeInTheDocument()
        expect(screen.queryByText("4 items")).not.toBeInTheDocument()
        expect(screen.queryByText(/^View all/)).not.toBeInTheDocument()
    })

    it("shows day-view events at 6 AM and 9 PM", async () => {
        const early = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 6, 0, 0, 0)
        const late = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 21, 0, 0, 0)
        const appointment = (id: string, name: string, start: Date) => ({
            id,
            appointment_type_name: "Initial Interview",
            client_name: name,
            client_email: `${id}@example.com`,
            client_phone: null,
            client_timezone: "America/Los_Angeles",
            scheduled_start: start.toISOString(),
            scheduled_end: new Date(start.getTime() + 30 * 60 * 1000).toISOString(),
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
        })
        mockUseUnifiedCalendarData.mockReturnValue({
            appointments: [
                appointment("appt-early", "Early Client", early),
                appointment("appt-late", "Late Client", late),
            ],
            appointmentsLoading: false,
            tasks: [],
            tasksLoading: false,
            googleEvents: [],
            calendarConnected: true,
            calendarError: null,
        })

        render(<UnifiedCalendar includeGoogleEvents={false} />)

        fireEvent.click(screen.getByRole("combobox", { name: "Calendar period" }))
        const dayOption = await screen.findByRole("option", { name: "Day" })
        fireEvent.mouseMove(dayOption)
        fireEvent.click(dayOption)

        const hours = await screen.findByTestId("day-view-hours")
        expect(hours.querySelectorAll("[data-hour]")).toHaveLength(24)
        const earlyRow = hours.querySelector('[data-hour="6"]') as HTMLElement
        const lateRow = hours.querySelector('[data-hour="21"]') as HTMLElement
        expect(within(earlyRow).getByText(/Early Client/)).toBeInTheDocument()
        expect(within(lateRow).getByText(/Late Client/)).toBeInTheDocument()
    })
})
