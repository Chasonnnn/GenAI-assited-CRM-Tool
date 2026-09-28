import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { DashboardFilterBar } from "../app/(app)/dashboard/components/dashboard-filter-bar"

const mockUseAuth = vi.fn()
const mockUseDashboardFilters = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useAssignees: () => ({
        data: [
            { id: "admin-1", name: "Test Admin" },
            { id: "intake-1", name: "Test Intake" },
            { id: "cm-1", name: "Test Case Manager" },
        ],
    }),
}))

vi.mock("../app/(app)/dashboard/context/dashboard-filters", () => ({
    useDashboardFilters: () => mockUseDashboardFilters(),
}))

function setFilters(assigneeId?: string) {
    mockUseDashboardFilters.mockReturnValue({
        filters: {
            dateRange: "all",
            customRange: { from: undefined, to: undefined },
            assigneeId,
        },
        setDateRange: vi.fn(),
        setCustomRange: vi.fn(),
        setAssigneeId: vi.fn(),
        resetFilters: vi.fn(),
    })
}

describe("DashboardFilterBar", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        setFilters()
    })

    it("lists the current admin once, as Mine", async () => {
        mockUseAuth.mockReturnValue({ user: { user_id: "admin-1", role: "admin" } })
        render(<DashboardFilterBar />)

        fireEvent.mouseDown(screen.getByRole("combobox", { name: "Filter by assignee" }))
        const listbox = await screen.findByRole("listbox")
        const options = within(listbox).getAllByRole("option").map((option) => option.textContent)

        expect(options).toEqual(["All Assignees", "Mine", "Test Intake", "Test Case Manager"])
    })

    it("labels the admin's own id as Mine in the trigger", () => {
        setFilters("admin-1")
        mockUseAuth.mockReturnValue({ user: { user_id: "admin-1", role: "admin" } })
        render(<DashboardFilterBar />)

        expect(screen.getByRole("combobox", { name: "Filter by assignee" })).toHaveTextContent("Mine")
    })

    it("hides the assignee filter for non-admin roles", () => {
        mockUseAuth.mockReturnValue({ user: { user_id: "intake-1", role: "intake_specialist" } })
        render(<DashboardFilterBar />)

        expect(screen.queryByRole("combobox", { name: "Filter by assignee" })).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Filter by date range" })).toBeInTheDocument()
    })

    it("gives the date and assignee triggers the same height and surface", () => {
        mockUseAuth.mockReturnValue({ user: { user_id: "admin-1", role: "admin" } })
        render(<DashboardFilterBar />)

        const dateTrigger = screen.getByRole("button", { name: "Filter by date range" })
        const assigneeTrigger = screen.getByRole("combobox", { name: "Filter by assignee" })

        expect(dateTrigger).toHaveClass("h-9", "bg-background")
        expect(assigneeTrigger).toHaveAttribute("data-size", "default")
        expect(assigneeTrigger).toHaveClass("bg-background")
        expect(assigneeTrigger).not.toHaveClass("bg-input/30")
    })
})
