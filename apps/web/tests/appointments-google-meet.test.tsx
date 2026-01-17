import type { PropsWithChildren } from "react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { AppointmentSettings } from "../components/appointments/AppointmentSettings"
import { PublicBookingPage } from "../components/appointments/PublicBookingPage"
import { AppointmentsList } from "../components/appointments/AppointmentsList"

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
        data: [{ integration_type: "gmail", connected: true }],
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
    Tabs: ({ children }: PropsWithChildren) => <div>{children}</div>,
    TabsList: ({ children }: PropsWithChildren) => <div>{children}</div>,
    TabsTrigger: ({ children }: PropsWithChildren) => (
        <button type="button">{children}</button>
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
    useCancelAppointment: () => ({
        mutate: mockUseCancelAppointment,
        isPending: false,
    }),
    usePublicBookingPage: (publicSlug: string, enabled?: boolean) =>
        mockUsePublicBookingPage(publicSlug, enabled),
    useAvailableSlots: (...args: unknown[]) => mockUseAvailableSlots(...args),
    useCreateBooking: () => ({
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
})
