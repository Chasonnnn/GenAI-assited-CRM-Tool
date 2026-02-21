import type { PropsWithChildren } from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { AppointmentSettings } from "../components/appointments/AppointmentSettings"
import { PublicBookingPage } from "../components/appointments/PublicBookingPage"
import { AppointmentsList } from "../components/appointments/AppointmentsList"
import AppointmentsPage from "../app/(app)/appointments/page"

const mockUseAppointmentTypes = vi.fn()
const mockUseCreateAppointmentType = vi.fn()
const mockUseUpdateAppointmentType = vi.fn()
const mockUseDeleteAppointmentType = vi.fn()
const mockUseAvailabilityRules = vi.fn()
const mockUseSetAvailabilityRules = vi.fn()
const mockUseBookingLink = vi.fn()
const mockUseRegenerateBookingLink = vi.fn()
const mockUseAppointments = vi.fn()
const mockUseAppointment = vi.fn()
const mockUseApproveAppointment = vi.fn()
const mockUseRescheduleAppointment = vi.fn()
const mockUseRescheduleSlots = vi.fn()
const mockUseCancelAppointment = vi.fn()
const mockUsePublicBookingPage = vi.fn()
const mockUseAvailableSlots = vi.fn()
const mockUseCreateBooking = vi.fn()
const mockUseBookingPreviewPage = vi.fn()
const mockUseBookingPreviewSlots = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: {
            user_id: "u1",
            display_name: "Test User",
            org_timezone: "America/Los_Angeles",
        },
    }),
}))

vi.mock("@/lib/hooks/use-user-integrations", () => ({
    useUserIntegrations: () => ({
        data: [{ integration_type: "google_calendar", connected: true }],
        isLoading: false,
        isError: false,
    }),
}))

vi.mock("@/components/ui/select", () => ({
    Select: ({
        value,
        onValueChange,
        children,
    }: PropsWithChildren<{
        value?: string
        onValueChange?: (value: string) => void
    }>) => (
        <div>
            <select
                data-testid="select"
                value={value ?? ""}
                onChange={(event) => onValueChange?.(event.target.value)}
            >
                <option value="">Select</option>
            </select>
            <div>{children}</div>
        </div>
    ),
    SelectTrigger: ({ children }: PropsWithChildren) => <div>{children}</div>,
    SelectValue: () => null,
    SelectContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
    SelectItem: ({
        value,
        children,
    }: PropsWithChildren<{ value: string }>) => (
        <div data-value={value}>{children}</div>
    ),
}))

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogDescription: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogHeader: ({ children }: PropsWithChildren) => <div>{children}</div>,
    DialogTitle: ({ children }: PropsWithChildren) => <h2>{children}</h2>,
}))

vi.mock("@/components/ui/tabs", () => ({
    Tabs: ({
        children,
        defaultValue,
    }: PropsWithChildren<{ defaultValue?: string }>) => (
        <div data-testid="tabs-root" data-default-value={defaultValue}>
            {children}
        </div>
    ),
    TabsList: ({ children }: PropsWithChildren) => <div>{children}</div>,
    TabsTrigger: ({
        children,
        value,
    }: PropsWithChildren<{ value?: string }>) => (
        <button type="button" data-value={value}>
            {children}
        </button>
    ),
    TabsContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
}))

vi.mock("@/lib/hooks/use-appointments", () => ({
    useBookingLink: () => mockUseBookingLink(),
    useRegenerateBookingLink: () => ({
        mutate: mockUseRegenerateBookingLink,
        isPending: false,
    }),
    useAppointmentTypes: () => mockUseAppointmentTypes(),
    useCreateAppointmentType: () => ({
        mutateAsync: mockUseCreateAppointmentType,
        isPending: false,
    }),
    useUpdateAppointmentType: () => ({
        mutateAsync: mockUseUpdateAppointmentType,
        isPending: false,
    }),
    useDeleteAppointmentType: () => ({
        mutate: mockUseDeleteAppointmentType,
        isPending: false,
    }),
    useAvailabilityRules: () => mockUseAvailabilityRules(),
    useSetAvailabilityRules: () => ({
        mutate: mockUseSetAvailabilityRules,
        isPending: false,
    }),
    useAppointments: (params: unknown) => mockUseAppointments(params),
    useAppointment: (appointmentId: string) => mockUseAppointment(appointmentId),
    useApproveAppointment: () => ({
        mutate: mockUseApproveAppointment,
        isPending: false,
    }),
    useRescheduleAppointment: () => ({
        mutate: mockUseRescheduleAppointment,
        isPending: false,
    }),
    useRescheduleSlots: (
        appointmentId: string,
        dateStart: string,
        dateEnd?: string,
        clientTimezone?: string,
        enabled = true
    ) => mockUseRescheduleSlots(appointmentId, dateStart, dateEnd, clientTimezone, enabled),
    useCancelAppointment: () => ({
        mutate: mockUseCancelAppointment,
        isPending: false,
    }),
    usePublicBookingPage: (publicSlug: string, enabled?: boolean) =>
        mockUsePublicBookingPage(publicSlug, enabled),
    useAvailableSlots: (...args: unknown[]) => mockUseAvailableSlots(...args),
    useCreateBooking: () => ({
        mutate: mockUseCreateBooking,
        mutateAsync: mockUseCreateBooking,
        isPending: false,
    }),
    useBookingPreviewPage: (enabled?: boolean) =>
        mockUseBookingPreviewPage(enabled),
    useBookingPreviewSlots: (...args: unknown[]) =>
        mockUseBookingPreviewSlots(...args),
}))

describe("Appointments Google Meet UI", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseAppointmentTypes.mockReturnValue({ data: [], isLoading: false })
        mockUseAvailabilityRules.mockReturnValue({ data: [], isLoading: false })
        mockUseBookingLink.mockReturnValue({
            data: { full_url: "https://example.com/book/abc", public_slug: "abc" },
            isLoading: false,
        })
        mockUseAppointments.mockReturnValue({
            data: { items: [], total: 0, page: 1, per_page: 50, pages: 0 },
            isLoading: false,
        })
        mockUseAppointment.mockReturnValue({ data: null, isLoading: false })
        mockUseRescheduleSlots.mockReturnValue({
            data: { slots: [], appointment_type: null },
            isLoading: false,
            isError: false,
        })
        mockUsePublicBookingPage.mockReturnValue({
            data: null,
            isLoading: false,
            error: null,
        })
        mockUseAvailableSlots.mockReturnValue({
            data: { slots: [], appointment_type: null },
            isLoading: false,
        })
        mockUseBookingPreviewPage.mockReturnValue({
            data: null,
            isLoading: false,
            error: null,
        })
        mockUseBookingPreviewSlots.mockReturnValue({
            data: { slots: [], appointment_type: null },
            isLoading: false,
        })
    })

    it("shows Google Meet as an appointment format option", () => {
        render(<AppointmentSettings />)
        expect(screen.getByText(/Google Meet/i)).toBeInTheDocument()
    })

    it("labels Google Meet appointment types on the public booking page", () => {
        mockUseBookingPreviewPage.mockReturnValue({
            data: {
                staff: {
                    user_id: "u1",
                    display_name: "Test User",
                    avatar_url: null,
                },
                appointment_types: [
                    {
                        id: "type1",
                        user_id: "u1",
                        name: "Intro Call",
                        slug: "intro-call",
                        description: null,
                        duration_minutes: 30,
                        buffer_before_minutes: 0,
                        buffer_after_minutes: 5,
                        meeting_mode: "google_meet",
                        meeting_modes: ["google_meet"],
                        meeting_location: null,
                        dial_in_number: null,
                        auto_approve: false,
                        reminder_hours_before: 24,
                        is_active: true,
                        created_at: "2024-01-01T00:00:00Z",
                        updated_at: "2024-01-01T00:00:00Z",
                    },
                ],
                org_name: "Demo Org",
                org_timezone: "America/Los_Angeles",
            },
            isLoading: false,
            error: null,
        })

        render(<PublicBookingPage publicSlug="preview" preview />)
        expect(screen.getByText(/Google Meet/i)).toBeInTheDocument()
    })

    it("requires a meeting format selection when multiple modes are available", () => {
        mockUseBookingPreviewPage.mockReturnValue({
            data: {
                staff: {
                    user_id: "u1",
                    display_name: "Test User",
                    avatar_url: null,
                },
                appointment_types: [
                    {
                        id: "type2",
                        user_id: "u1",
                        name: "Discovery Call",
                        slug: "discovery-call",
                        description: null,
                        duration_minutes: 30,
                        buffer_before_minutes: 0,
                        buffer_after_minutes: 5,
                        meeting_mode: "zoom",
                        meeting_modes: ["zoom", "google_meet"],
                        meeting_location: null,
                        dial_in_number: null,
                        auto_approve: false,
                        reminder_hours_before: 24,
                        is_active: true,
                        created_at: "2024-01-01T00:00:00Z",
                        updated_at: "2024-01-01T00:00:00Z",
                    },
                ],
                org_name: "Demo Org",
                org_timezone: "America/Los_Angeles",
            },
            isLoading: false,
            error: null,
        })

        render(<PublicBookingPage publicSlug="preview" preview />)

        fireEvent.click(screen.getByRole("button", { name: /Discovery Call/i }))

        expect(screen.getByText(/Select Appointment Format/i)).toBeInTheDocument()
        expect(screen.queryByText(/Select a Date/i)).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /Google Meet/i }))
        expect(screen.getByText(/Select a Date/i)).toBeInTheDocument()
    })

    it("shows Google Meet join link in appointment details", () => {
        const scheduledStart = new Date("2024-02-01T18:00:00Z").toISOString()
        const scheduledEnd = new Date("2024-02-01T18:30:00Z").toISOString()
        mockUseAppointments.mockReturnValue({
            data: {
                items: [
                    {
                        id: "appt1",
                        appointment_type_name: "Intro Call",
                        client_name: "Casey Client",
                        client_email: "casey@example.com",
                        client_phone: "555-0100",
                        client_timezone: "America/Los_Angeles",
                        scheduled_start: scheduledStart,
                        scheduled_end: scheduledEnd,
                        duration_minutes: 30,
                        meeting_mode: "google_meet",
                        status: "confirmed",
                        surrogate_id: null,
                        surrogate_number: null,
                        intended_parent_id: null,
                        intended_parent_name: null,
                        created_at: scheduledStart,
                    },
                ],
                total: 1,
                page: 1,
                per_page: 50,
                pages: 1,
            },
            isLoading: false,
        })
        mockUseAppointment.mockReturnValue({
            data: {
                id: "appt1",
                user_id: "u1",
                appointment_type_id: "type1",
                appointment_type_name: "Intro Call",
                client_name: "Casey Client",
                client_email: "casey@example.com",
                client_phone: "555-0100",
                client_timezone: "America/Los_Angeles",
                client_notes: null,
                scheduled_start: scheduledStart,
                scheduled_end: scheduledEnd,
                duration_minutes: 30,
                meeting_mode: "google_meet",
                status: "confirmed",
                pending_expires_at: null,
                approved_at: scheduledStart,
                approved_by_user_id: "u1",
                approved_by_name: "Test User",
                cancelled_at: null,
                cancelled_by_client: false,
                cancellation_reason: null,
                zoom_join_url: null,
                google_event_id: "event-123",
                google_meet_url: "https://meet.google.com/abc-defg-hij",
                surrogate_id: null,
                surrogate_number: null,
                intended_parent_id: null,
                intended_parent_name: null,
                created_at: scheduledStart,
                updated_at: scheduledStart,
            },
            isLoading: false,
        })

        render(<AppointmentsList />)
        fireEvent.click(screen.getAllByText("Casey Client")[0])

        expect(screen.getByText(/Join Google Meet/i)).toBeInTheDocument()
    })

    it("shows reschedule action in appointment details", () => {
        const scheduledStart = new Date("2026-02-23T20:00:00Z").toISOString()
        const scheduledEnd = new Date("2026-02-23T20:30:00Z").toISOString()

        mockUseAppointments.mockReturnValue({
            data: {
                items: [
                    {
                        id: "appt-reschedule",
                        appointment_type_name: "Initial Interview",
                        client_name: "Test Zhang",
                        client_email: "chason1127@gmail.com",
                        client_phone: "8052848667",
                        client_timezone: "America/Los_Angeles",
                        scheduled_start: scheduledStart,
                        scheduled_end: scheduledEnd,
                        duration_minutes: 30,
                        meeting_mode: "google_meet",
                        status: "confirmed",
                        surrogate_id: null,
                        surrogate_number: null,
                        intended_parent_id: null,
                        intended_parent_name: null,
                        created_at: scheduledStart,
                    },
                ],
                total: 1,
                page: 1,
                per_page: 50,
                pages: 1,
            },
            isLoading: false,
        })
        mockUseAppointment.mockReturnValue({
            data: {
                id: "appt-reschedule",
                user_id: "u1",
                appointment_type_id: "type1",
                appointment_type_name: "Initial Interview",
                client_name: "Test Zhang",
                client_email: "chason1127@gmail.com",
                client_phone: "8052848667",
                client_timezone: "America/Los_Angeles",
                client_notes: "test",
                scheduled_start: scheduledStart,
                scheduled_end: scheduledEnd,
                duration_minutes: 30,
                meeting_mode: "google_meet",
                status: "confirmed",
                pending_expires_at: null,
                approved_at: scheduledStart,
                approved_by_user_id: "u1",
                approved_by_name: "Test User",
                cancelled_at: null,
                cancelled_by_client: false,
                cancellation_reason: null,
                zoom_join_url: null,
                google_event_id: "event-123",
                google_meet_url: "https://meet.google.com/abc-defg-hij",
                surrogate_id: null,
                surrogate_number: null,
                intended_parent_id: null,
                intended_parent_name: null,
                created_at: scheduledStart,
                updated_at: scheduledStart,
            },
            isLoading: false,
        })

        render(<AppointmentsList />)
        fireEvent.click(screen.getAllByText("Test Zhang")[0])

        expect(screen.getByRole("button", { name: /reschedule appointment/i })).toBeInTheDocument()
    })

    it("submits reschedule mutation from appointment details", () => {
        const scheduledStart = new Date("2026-02-23T20:00:00Z").toISOString()
        const scheduledEnd = new Date("2026-02-23T20:30:00Z").toISOString()
        const selectedSlotStart = "2026-02-24T17:15:00.000Z"
        mockUseRescheduleSlots.mockReturnValue({
            data: {
                slots: [{ start: selectedSlotStart, end: "2026-02-24T17:45:00.000Z" }],
                appointment_type: null,
            },
            isLoading: false,
            isError: false,
        })

        mockUseAppointments.mockReturnValue({
            data: {
                items: [
                    {
                        id: "appt-reschedule-submit",
                        appointment_type_name: "Initial Interview",
                        client_name: "Test Zhang",
                        client_email: "chason1127@gmail.com",
                        client_phone: "8052848667",
                        client_timezone: "America/Los_Angeles",
                        scheduled_start: scheduledStart,
                        scheduled_end: scheduledEnd,
                        duration_minutes: 30,
                        meeting_mode: "google_meet",
                        status: "confirmed",
                        surrogate_id: null,
                        surrogate_number: null,
                        intended_parent_id: null,
                        intended_parent_name: null,
                        created_at: scheduledStart,
                    },
                ],
                total: 1,
                page: 1,
                per_page: 50,
                pages: 1,
            },
            isLoading: false,
        })
        mockUseAppointment.mockReturnValue({
            data: {
                id: "appt-reschedule-submit",
                user_id: "u1",
                appointment_type_id: "type1",
                appointment_type_name: "Initial Interview",
                client_name: "Test Zhang",
                client_email: "chason1127@gmail.com",
                client_phone: "8052848667",
                client_timezone: "America/Los_Angeles",
                client_notes: "test",
                scheduled_start: scheduledStart,
                scheduled_end: scheduledEnd,
                duration_minutes: 30,
                meeting_mode: "google_meet",
                status: "confirmed",
                pending_expires_at: null,
                approved_at: scheduledStart,
                approved_by_user_id: "u1",
                approved_by_name: "Test User",
                cancelled_at: null,
                cancelled_by_client: false,
                cancellation_reason: null,
                zoom_join_url: null,
                google_event_id: "event-123",
                google_meet_url: "https://meet.google.com/abc-defg-hij",
                surrogate_id: null,
                surrogate_number: null,
                intended_parent_id: null,
                intended_parent_name: null,
                created_at: scheduledStart,
                updated_at: scheduledStart,
            },
            isLoading: false,
        })

        render(<AppointmentsList />)
        fireEvent.click(screen.getAllByText("Test Zhang")[0])

        fireEvent.click(screen.getByRole("button", { name: /reschedule appointment/i }))
        fireEvent.click(screen.getByRole("button", { name: `Reschedule slot ${selectedSlotStart}` }))
        fireEvent.click(screen.getByRole("button", { name: /confirm reschedule/i }))

        expect(mockUseRescheduleAppointment).toHaveBeenCalled()
        const payload = mockUseRescheduleAppointment.mock.calls[0]?.[0]
        expect(payload.appointmentId).toBe("appt-reschedule-submit")
        expect(payload.scheduledStart).toBe(selectedSlotStart)
    })

    it("shows reschedule error message in appointment details", () => {
        const scheduledStart = new Date("2026-02-23T20:00:00Z").toISOString()
        const scheduledEnd = new Date("2026-02-23T20:30:00Z").toISOString()
        const selectedSlotStart = "2026-02-24T17:15:00.000Z"
        mockUseRescheduleSlots.mockReturnValue({
            data: {
                slots: [{ start: selectedSlotStart, end: "2026-02-24T17:45:00.000Z" }],
                appointment_type: null,
            },
            isLoading: false,
            isError: false,
        })
        mockUseRescheduleAppointment.mockImplementation((_: unknown, options?: {
            onError?: (error: Error) => void
        }) => {
            options?.onError?.(new Error("Selected time is no longer available."))
        })

        mockUseAppointments.mockReturnValue({
            data: {
                items: [
                    {
                        id: "appt-reschedule-error",
                        appointment_type_name: "Initial Interview",
                        client_name: "Test Zhang",
                        client_email: "chason1127@gmail.com",
                        client_phone: "8052848667",
                        client_timezone: "America/Los_Angeles",
                        scheduled_start: scheduledStart,
                        scheduled_end: scheduledEnd,
                        duration_minutes: 30,
                        meeting_mode: "google_meet",
                        status: "confirmed",
                        surrogate_id: null,
                        surrogate_number: null,
                        intended_parent_id: null,
                        intended_parent_name: null,
                        created_at: scheduledStart,
                    },
                ],
                total: 1,
                page: 1,
                per_page: 50,
                pages: 1,
            },
            isLoading: false,
        })
        mockUseAppointment.mockReturnValue({
            data: {
                id: "appt-reschedule-error",
                user_id: "u1",
                appointment_type_id: "type1",
                appointment_type_name: "Initial Interview",
                client_name: "Test Zhang",
                client_email: "chason1127@gmail.com",
                client_phone: "8052848667",
                client_timezone: "America/Los_Angeles",
                client_notes: "test",
                scheduled_start: scheduledStart,
                scheduled_end: scheduledEnd,
                duration_minutes: 30,
                meeting_mode: "google_meet",
                status: "confirmed",
                pending_expires_at: null,
                approved_at: scheduledStart,
                approved_by_user_id: "u1",
                approved_by_name: "Test User",
                cancelled_at: null,
                cancelled_by_client: false,
                cancellation_reason: null,
                zoom_join_url: null,
                google_event_id: "event-123",
                google_meet_url: "https://meet.google.com/abc-defg-hij",
                surrogate_id: null,
                surrogate_number: null,
                intended_parent_id: null,
                intended_parent_name: null,
                created_at: scheduledStart,
                updated_at: scheduledStart,
            },
            isLoading: false,
        })

        render(<AppointmentsList />)
        fireEvent.click(screen.getAllByText("Test Zhang")[0])

        fireEvent.click(screen.getByRole("button", { name: /reschedule appointment/i }))
        fireEvent.click(screen.getByRole("button", { name: `Reschedule slot ${selectedSlotStart}` }))
        fireEvent.click(screen.getByRole("button", { name: /confirm reschedule/i }))

        expect(screen.getByRole("alert")).toHaveTextContent("Selected time is no longer available.")
    })

    it("defaults appointments to upcoming tab and shows upcoming first", () => {
        render(<AppointmentsList />)

        const tabsRoot = screen.getByTestId("tabs-root")
        expect(tabsRoot).toHaveAttribute("data-default-value", "confirmed")

        const triggers = screen.getAllByRole("button").slice(0, 5)
        expect(triggers.map((trigger) => trigger.textContent?.trim())).toEqual([
            "Upcoming",
            "Pending",
            "Past",
            "Cancelled",
            "Expired",
        ])
        expect(triggers.map((trigger) => trigger.getAttribute("data-value"))).toEqual([
            "confirmed",
            "pending",
            "completed",
            "cancelled",
            "expired",
        ])
    })

    it("keeps public booking idempotency keys within 64 characters", async () => {
        const now = new Date()
        const slotDate = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0))
        const slotStart = slotDate.toISOString()
        const slotEnd = new Date(slotDate.getTime() + 30 * 60 * 1000).toISOString()

        mockUsePublicBookingPage.mockReturnValue({
            data: {
                staff: {
                    user_id: "u1",
                    display_name: "Test User",
                    avatar_url: null,
                },
                appointment_types: [
                    {
                        id: "1b9d94fc-d501-4814-b486-2561d46d4cad",
                        user_id: "u1",
                        name: "Intro Call",
                        slug: "intro-call",
                        description: null,
                        duration_minutes: 30,
                        buffer_before_minutes: 0,
                        buffer_after_minutes: 5,
                        meeting_mode: "google_meet",
                        meeting_location: null,
                        dial_in_number: null,
                        auto_approve: false,
                        reminder_hours_before: 24,
                        is_active: true,
                        created_at: "2026-01-01T00:00:00Z",
                        updated_at: "2026-01-01T00:00:00Z",
                    },
                ],
                org_name: "Demo Org",
                org_timezone: "America/Los_Angeles",
            },
            isLoading: false,
            error: null,
        })
        mockUseAvailableSlots.mockReturnValue({
            data: {
                slots: [
                    {
                        start: slotStart,
                        end: slotEnd,
                    },
                ],
                appointment_type: null,
            },
            isLoading: false,
        })

        render(<PublicBookingPage publicSlug="MpJIj9PkxNTpLNSS" />)

        fireEvent.click(screen.getByRole("button", { name: /Intro Call/i }))

        const dayButton = screen
            .getAllByRole("button")
            .find((button) => {
                const label = button.textContent?.trim() || ""
                return /^\d+$/.test(label) && !button.hasAttribute("disabled")
            })
        expect(dayButton).toBeTruthy()
        fireEvent.click(dayButton!)

        const timeButton = await screen.findByRole("button", { name: /:00/ })
        fireEvent.click(timeButton)

        fireEvent.click(screen.getByRole("button", { name: /Continue/i }))

        fireEvent.change(screen.getByLabelText(/Full Name/i), {
            target: { value: "Chason Zhang" },
        })
        fireEvent.change(screen.getByLabelText(/Email/i), {
            target: { value: "chason1127@gmail.com" },
        })
        fireEvent.change(screen.getByLabelText(/Phone Number/i), {
            target: { value: "8052848667" },
        })

        fireEvent.click(screen.getByRole("button", { name: /Request Appointment/i }))

        const payload = mockUseCreateBooking.mock.calls[0]?.[0]
        expect(payload?.data?.idempotency_key).toBeTruthy()
        expect(payload.data.idempotency_key.length).toBeLessThanOrEqual(64)

    })

    it("renders appointments list error state with retry", () => {
        const refetch = vi.fn()
        mockUseAppointments.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new Error("Network error"),
            refetch,
        })

        render(<AppointmentsList />)

        expect(screen.getAllByText(/Unable to load appointments/i).length).toBeGreaterThan(0)
        fireEvent.click(screen.getAllByRole("button", { name: /retry/i })[0])
        expect(refetch).toHaveBeenCalled()
    })

    it("shows appointment detail error state", () => {
        const scheduledStart = new Date("2024-02-01T18:00:00Z").toISOString()
        const scheduledEnd = new Date("2024-02-01T18:30:00Z").toISOString()
        const refetch = vi.fn()
        mockUseAppointments.mockReturnValue({
            data: {
                items: [
                    {
                        id: "appt1",
                        appointment_type_name: "Intro Call",
                        client_name: "Casey Client",
                        client_email: "casey@example.com",
                        client_phone: "555-0100",
                        client_timezone: "America/Los_Angeles",
                        scheduled_start: scheduledStart,
                        scheduled_end: scheduledEnd,
                        duration_minutes: 30,
                        meeting_mode: "google_meet",
                        status: "confirmed",
                        surrogate_id: null,
                        surrogate_number: null,
                        intended_parent_id: null,
                        intended_parent_name: null,
                        created_at: scheduledStart,
                    },
                ],
                total: 1,
                page: 1,
                per_page: 50,
                pages: 1,
            },
            isLoading: false,
        })
        mockUseAppointment.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new Error("Detail error"),
            refetch,
        })

        render(<AppointmentsList />)
        fireEvent.click(screen.getAllByText("Casey Client")[0])

        expect(screen.getByText(/Unable to load appointment details/i)).toBeInTheDocument()
        fireEvent.click(screen.getAllByRole("button", { name: /retry/i })[0])
        expect(refetch).toHaveBeenCalled()
    })

    it("renders booking link error state with retry", () => {
        const refetch = vi.fn()
        mockUseBookingLink.mockReturnValue({
            data: null,
            isLoading: false,
            isError: true,
            error: new Error("Booking link error"),
            refetch,
        })

        render(<AppointmentsPage />)

        expect(screen.getByText(/Unable to load booking link/i)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: /retry/i }))
        expect(refetch).toHaveBeenCalled()
    })
})
