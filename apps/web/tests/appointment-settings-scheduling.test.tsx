import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import { AppointmentSettings } from "@/components/appointments/AppointmentSettings"

const mocks = vi.hoisted(() => ({
    search: "",
    rules: vi.fn(),
    types: vi.fn(),
    create: vi.fn(),
    toast: { success: vi.fn(), error: vi.fn(), dismiss: vi.fn() },
}))

vi.mock("next/navigation", () => ({
    useSearchParams: () => new URLSearchParams(mocks.search),
    usePathname: () => "/settings/appointments",
}))
vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { user_id: "u1", org_timezone: "America/New_York" } }),
}))
vi.mock("@/lib/hooks/use-user-integrations", () => ({
    useUserIntegrations: () => ({ data: [{ integration_type: "google_calendar", connected: true }], isLoading: false, isError: false }),
}))
vi.mock("@/components/ui/toast", () => ({ toast: mocks.toast }))
vi.mock("@/lib/hooks/use-appointments", () => ({
    useBookingLink: () => ({ data: { full_url: "https://example.com/book/abc", public_slug: "abc" }, isLoading: false }),
    useRegenerateBookingLink: () => ({ mutate: vi.fn(), isPending: false }),
    useAvailabilityRules: () => mocks.rules(),
    useSetAvailabilityRules: () => ({ mutate: vi.fn(), isPending: false }),
    useAppointmentTypes: () => mocks.types(),
    useCreateAppointmentType: () => ({ mutateAsync: mocks.create, isPending: false }),
    useUpdateAppointmentType: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteAppointmentType: () => ({ mutate: vi.fn(), isPending: false }),
}))

describe("AppointmentSettings scheduling fixes", () => {
    beforeEach(() => {
        mocks.search = ""
        mocks.rules.mockReset().mockReturnValue({ data: [], isLoading: false })
        mocks.types.mockReset().mockReturnValue({ data: [], isLoading: false })
        mocks.create.mockReset().mockResolvedValue({})
        Object.values(mocks.toast).forEach((fn) => fn.mockReset())
        window.history.replaceState(null, "", "/settings/appointments")
    })

    it("shows API times with seconds as readable labels instead of Unknown", () => {
        mocks.rules.mockReturnValue({
            data: [{ id: "rule-1", day_of_week: 0, start_time: "09:00:00", end_time: "17:30:00", timezone: "America/New_York" }],
            isLoading: false,
        })
        render(<AppointmentSettings />)

        expect(screen.getByRole("combobox", { name: "Monday start time" })).toHaveTextContent("9:00 AM")
        expect(screen.getByRole("combobox", { name: "Monday end time" })).toHaveTextContent("5:30 PM")
        expect(screen.queryByText(/Unknown/)).not.toBeInTheDocument()
    })

    it("keeps the tab list compact and reads the active tab from the URL", () => {
        mocks.search = "tab=types"
        render(<AppointmentSettings />)

        const tabList = screen.getByRole("tablist")
        // Compare whole class tokens: the primitive's max-w-full cap is fine, a stretched list is not.
        const tabListClasses = tabList.className.split(/\s+/)
        expect(tabListClasses).toContain("w-fit")
        expect(tabListClasses).not.toContain("w-full")
        expect(tabListClasses).not.toContain("grid")
        expect(screen.getByRole("tab", { name: "Appointment Types" })).toHaveAttribute("aria-selected", "true")

        const replaceState = vi.spyOn(window.history, "replaceState")
        fireEvent.click(screen.getByRole("tab", { name: "Booking Link" }))
        expect(replaceState).toHaveBeenCalledWith(null, "", "/settings/appointments?tab=link")
        replaceState.mockRestore()
    })

    it("uses sentence case for the booking page preview button", () => {
        mocks.search = "tab=link"
        render(<AppointmentSettings />)

        expect(screen.getByRole("button", { name: "Preview booking page" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Preview Booking Page" })).not.toBeInTheDocument()
    })

    it("shows a neutral empty state with a create action for appointment types", () => {
        mocks.search = "tab=types"
        render(<AppointmentSettings />)

        expect(screen.getByText("No appointment types")).toBeInTheDocument()
        const empty = screen.getByText("No appointment types").closest('[data-slot="empty-state"]') as HTMLElement
        fireEvent.click(within(empty).getByRole("button", { name: "Add type" }))
        expect(screen.getByRole("dialog", { name: "New Appointment Type" })).toBeInTheDocument()
    })

    it("validates every appointment type field at once, inline, without a toast", async () => {
        mocks.search = "tab=types"
        render(<AppointmentSettings />)

        fireEvent.click(screen.getAllByRole("button", { name: "Add type" })[0]!)
        const dialog = screen.getByRole("dialog", { name: "New Appointment Type" })
        // Sectioned layout: the body scrolls and the footer stays visible (scheduling-7).
        expect(dialog.querySelector('[data-slot="dialog-body"]')).not.toBeNull()

        fireEvent.click(within(dialog).getByRole("checkbox", { name: "In-Person" }))
        fireEvent.click(within(dialog).getByRole("checkbox", { name: "Phone" }))
        fireEvent.click(within(dialog).getByRole("button", { name: "Create type" }))

        expect(within(dialog).getByRole("textbox", { name: "Name" })).toHaveAttribute("aria-invalid", "true")
        expect(within(dialog).getByText("Enter a name.")).toBeInTheDocument()
        expect(within(dialog).getByRole("textbox", { name: "Location" })).toHaveAttribute("aria-invalid", "true")
        expect(within(dialog).getByText("Enter a location for in-person appointments.")).toBeInTheDocument()
        expect(within(dialog).getByRole("textbox", { name: "Dial-in Number" })).toHaveAttribute("aria-invalid", "true")
        expect(within(dialog).getByText("Enter a dial-in number for phone appointments.")).toBeInTheDocument()
        await waitFor(() => expect(within(dialog).getByRole("textbox", { name: "Name" })).toHaveFocus())
        expect(mocks.toast.error).not.toHaveBeenCalled()
        expect(mocks.create).not.toHaveBeenCalled()
    })
})
