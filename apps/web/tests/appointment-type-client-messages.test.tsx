import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import { AppointmentSettings } from "@/components/appointments/AppointmentSettings"
import type { AppointmentType } from "@/lib/api/appointments"

const mocks = vi.hoisted(() => ({
    types: vi.fn(),
    update: vi.fn(),
    workflows: vi.fn(),
    permissions: vi.fn(),
}))

vi.mock("next/navigation", () => ({
    useSearchParams: () => new URLSearchParams("tab=types"),
    usePathname: () => "/settings/appointments",
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
}))
vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { user_id: "u1", org_timezone: "America/New_York" } }),
}))
vi.mock("@/lib/hooks/use-user-integrations", () => ({
    useUserIntegrations: () => ({ data: [{ integration_type: "google_calendar", connected: true }], isLoading: false }),
}))
vi.mock("@/components/ui/toast", () => ({ toast: { success: vi.fn(), error: vi.fn(), dismiss: vi.fn() } }))
vi.mock("@/lib/hooks/use-appointments", () => ({
    useBookingLink: () => ({ data: undefined, isLoading: true }),
    useRegenerateBookingLink: () => ({ mutate: vi.fn(), isPending: false }),
    useAvailabilityRules: () => ({ data: [], isLoading: false }),
    useSetAvailabilityRules: () => ({ mutate: vi.fn(), isPending: false }),
    useAppointmentTypes: () => mocks.types(),
    useCreateAppointmentType: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateAppointmentType: () => ({ mutateAsync: mocks.update, isPending: false }),
    useDeleteAppointmentType: () => ({ mutate: vi.fn(), isPending: false }),
}))
vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplates: () => ({
        data: [
            { id: "tpl-consult", name: "Consult Confirmed" },
            { id: "tpl-default", name: "Booking Confirmed", system_key: "scheduling_confirmed" },
        ],
        isLoading: false,
    }),
}))
vi.mock("@/lib/hooks/use-workflows", () => ({
    useWorkflows: (params: unknown) => mocks.workflows(params),
}))
vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => mocks.permissions(),
}))

const CONSULTATION: AppointmentType = {
    id: "type-1",
    user_id: "u1",
    name: "Initial Consultation",
    slug: "initial-consultation",
    description: null,
    duration_minutes: 45,
    buffer_before_minutes: 0,
    buffer_after_minutes: 5,
    meeting_mode: "phone",
    meeting_modes: ["phone"],
    meeting_location: null,
    dial_in_number: "555-0100",
    auto_approve: false,
    reminder_hours_before: 48,
    client_messages: {
        request_received: { enabled: true, template_id: null },
        confirmed: { enabled: true, template_id: "tpl-consult" },
        reminder: { enabled: true, template_id: null },
        rescheduled: { enabled: true, template_id: null },
        cancelled: { enabled: false, template_id: null },
    },
    is_active: true,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
}

function openEditDialog() {
    render(<AppointmentSettings />)
    fireEvent.click(screen.getByRole("button", { name: "Edit" }))
    return screen.getByRole("dialog", { name: "Edit Appointment Type" })
}

describe("Appointment type client messages and workflows", () => {
    beforeEach(() => {
        mocks.types.mockReset().mockReturnValue({ data: [CONSULTATION], isLoading: false })
        mocks.update.mockReset().mockResolvedValue(CONSULTATION)
        mocks.workflows.mockReset().mockReturnValue({
            data: [
                {
                    id: "wf-1",
                    name: "Move to Consult Scheduled",
                    trigger_type: "appointment_scheduled",
                    is_enabled: true,
                },
                {
                    id: "wf-2",
                    name: "No-show follow-up",
                    trigger_type: "appointment_no_show",
                    is_enabled: false,
                },
            ],
            isLoading: false,
            isError: false,
        })
        mocks.permissions.mockReset().mockReturnValue({
            can: (permission: string) => permission === "manage_automation",
            policyVersion: 1,
        })
    })

    it("shows each client message with its switch, template, and reminder timing", () => {
        const dialog = openEditDialog()

        for (const label of ["Request received", "Confirmed", "Reminder", "Rescheduled"]) {
            expect(within(dialog).getByRole("switch", { name: label })).toHaveAttribute("aria-checked", "true")
        }
        expect(within(dialog).getByRole("switch", { name: "Cancelled" })).toHaveAttribute("aria-checked", "false")
        expect(within(dialog).getByRole("combobox", { name: "Confirmed template" })).toHaveTextContent(
            "Consult Confirmed",
        )
        expect(within(dialog).getByRole("combobox", { name: "Request received template" })).toHaveTextContent(
            "Default template",
        )
        expect(within(dialog).getByRole("combobox", { name: "Reminder timing" })).toHaveTextContent(
            "48 hours before",
        )
        expect(
            within(dialog).getByText(
                "Google Calendar events use Google invites instead of Confirmed, Rescheduled, and Cancelled.",
            ),
        ).toBeInTheDocument()
    })

    it("offers the org templates but not scheduling's own default templates", async () => {
        const dialog = openEditDialog()
        fireEvent.click(within(dialog).getByRole("combobox", { name: "Confirmed template" }))

        expect(await screen.findByRole("option", { name: "Consult Confirmed" })).toBeInTheDocument()
        expect(screen.getByRole("option", { name: "Default template" })).toBeInTheDocument()
        expect(screen.queryByRole("option", { name: "Booking Confirmed" })).not.toBeInTheDocument()
    })

    it("saves switch changes with the rest of the type", async () => {
        const dialog = openEditDialog()

        fireEvent.click(within(dialog).getByRole("switch", { name: "Reminder" }))
        expect(within(dialog).getByRole("combobox", { name: "Reminder timing" })).toBeDisabled()
        fireEvent.click(within(dialog).getByRole("switch", { name: "Cancelled" }))
        fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }))

        await waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1))
        expect(mocks.update.mock.calls[0]![0]).toMatchObject({
            typeId: "type-1",
            data: {
                reminder_hours_before: 48,
                client_messages: {
                    ...CONSULTATION.client_messages,
                    reminder: { enabled: false, template_id: null },
                    cancelled: { enabled: true, template_id: null },
                },
            },
        })
    })

    it("lists the type's workflows and starts a new one on this type", () => {
        const dialog = openEditDialog()

        expect(mocks.workflows).toHaveBeenCalledWith({ appointment_type_name: "Initial Consultation" })
        const scheduled = within(dialog).getByRole("link", { name: "Move to Consult Scheduled" })
        expect(scheduled).toHaveAttribute("href", "/automation/workflows/wf-1")
        expect(scheduled.closest("li")).toHaveTextContent("Appointment Scheduled")
        expect(scheduled.closest("li")).toHaveTextContent("Active")
        expect(within(dialog).getByRole("link", { name: "No-show follow-up" }).closest("li")).toHaveTextContent("Off")
        expect(within(dialog).getByRole("link", { name: "New workflow" })).toHaveAttribute(
            "href",
            "/automation/workflows/new?scope=org&trigger=appointment_scheduled&appointment_type=Initial+Consultation",
        )
    })

    it("starts a personal workflow without org workflow access and shows an empty list", () => {
        mocks.permissions.mockReturnValue({ can: () => false, policyVersion: 2 })
        mocks.workflows.mockReturnValue({ data: [], isLoading: false, isError: false })

        const dialog = openEditDialog()

        expect(within(dialog).getByText("No workflows")).toBeInTheDocument()
        expect(within(dialog).getByRole("link", { name: "New workflow" }).getAttribute("href")).toContain(
            "scope=personal",
        )
    })

    it("hides workflows for a type that is not saved yet", () => {
        render(<AppointmentSettings />)
        fireEvent.click(screen.getAllByRole("button", { name: "Add type" })[0]!)
        const dialog = screen.getByRole("dialog", { name: "New Appointment Type" })

        expect(within(dialog).getByRole("switch", { name: "Confirmed" })).toHaveAttribute("aria-checked", "true")
        expect(within(dialog).queryByRole("link", { name: "New workflow" })).not.toBeInTheDocument()
    })
})
