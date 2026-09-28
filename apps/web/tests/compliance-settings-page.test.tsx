import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"
import ComplianceSettingsPage from "../app/(app)/settings/compliance/page"

const useRetentionPoliciesMock = vi.fn()
const useLegalHoldsMock = vi.fn()
const upsertPolicyMock = vi.fn()
const executePurgeMock = vi.fn()
const canMock = vi.fn()
const toastError = vi.fn()
const toastSuccess = vi.fn()
let mockRole = "admin"

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { role: mockRole } }),
}))

vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => canMock(permission),
    }),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: (...args: unknown[]) => toastSuccess(...args),
        error: (...args: unknown[]) => toastError(...args),
    },
}))

vi.mock("@/lib/hooks/use-compliance", () => ({
    useRetentionPolicies: () => useRetentionPoliciesMock(),
    useUpsertRetentionPolicy: () => ({ mutateAsync: upsertPolicyMock, isPending: false }),
    useLegalHolds: (params: { page: number; per_page: number }) =>
        useLegalHoldsMock(params),
    useCreateLegalHold: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useReleaseLegalHold: () => ({ mutateAsync: vi.fn(), isPending: false }),
    usePurgePreview: () => ({ data: { items: [] }, refetch: vi.fn() }),
    useExecutePurge: () => ({ mutateAsync: executePurgeMock }),
}))

function policy(entityType: string, retentionDays: number, isActive = true) {
    return {
        id: `policy-${entityType}`,
        entity_type: entityType,
        retention_days: retentionDays,
        is_active: isActive,
        created_by_user_id: null,
        created_at: "2026-06-01T12:00:00.000Z",
        updated_at: "2026-06-01T12:00:00.000Z",
    }
}

describe("Compliance settings page", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockRole = "admin"
        canMock.mockImplementation((permission: string) => permission === "manage_compliance")
        upsertPolicyMock.mockResolvedValue({})
        useRetentionPoliciesMock.mockReturnValue({
            data: [policy("donors", 30), policy("surrogates", 30), policy("tasks", 45)],
            isLoading: false,
        })
        useLegalHoldsMock.mockReturnValue({
            data: { items: [], total: 0, page: 1, per_page: 20, pages: 1 },
            isLoading: false,
        })
    })

    it("exposes donor retention and legal-hold controls", async () => {
        render(<ComplianceSettingsPage />)

        expect(await screen.findByRole("spinbutton", {
            name: "Donors (archived only) retention days",
        })).toHaveValue(30)

        fireEvent.click(screen.getByRole("combobox", { name: "Hold Scope" }))
        expect(await screen.findByRole("option", { name: "Donor" })).toBeInTheDocument()
    })

    it("adopts refreshed policies without overwriting an edited field", async () => {
        const view = render(<ComplianceSettingsPage />)

        const surrogateDays = await screen.findByRole("spinbutton", {
            name: "Surrogates (archived only) retention days",
        })
        const taskDays = screen.getByRole("spinbutton", {
            name: "Tasks (completed only) retention days",
        })
        const taskActive = screen.getByRole("switch", {
            name: "Tasks (completed only) retention active",
        })
        expect(surrogateDays).toHaveValue(30)
        expect(taskDays).toHaveValue(45)

        fireEvent.change(taskDays, { target: { value: "44" } })
        expect(taskDays).toHaveValue(44)

        useRetentionPoliciesMock.mockReturnValue({
            data: [policy("surrogates", 60), policy("tasks", 90, false)],
            isLoading: false,
        })
        view.rerender(<ComplianceSettingsPage />)

        await waitFor(() => expect(surrogateDays).toHaveValue(60))
        expect(taskDays).toHaveValue(44)
        expect(taskActive).not.toBeChecked()
    })

    it("returns to the first legal-holds page after results temporarily become empty", async () => {
        let legalHolds = {
            items: [],
            total: 40,
            page: 1,
            per_page: 20,
            pages: 2,
        }
        useLegalHoldsMock.mockImplementation(() => ({
            data: legalHolds,
            isLoading: false,
        }))

        const view = render(<ComplianceSettingsPage />)

        fireEvent.click(await screen.findByRole("button", { name: "2" }))
        expect(screen.getByText("Showing 21-40 of 40 legal holds")).toBeInTheDocument()

        legalHolds = {
            items: [],
            total: 0,
            page: 1,
            per_page: 20,
            pages: 0,
        }
        view.rerender(<ComplianceSettingsPage />)
        expect(screen.queryByText(/Showing .* legal holds/)).not.toBeInTheDocument()

        legalHolds = {
            items: [],
            total: 40,
            page: 1,
            per_page: 20,
            pages: 2,
        }
        view.rerender(<ComplianceSettingsPage />)

        expect(screen.getByText("Showing 1-20 of 40 legal holds")).toBeInTheDocument()
    })

    it("shows the denied state and loads nothing without manage_compliance", () => {
        canMock.mockReturnValue(false)

        render(<ComplianceSettingsPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Compliance" })).toBeInTheDocument()
        expect(screen.getByText("Permission required")).toBeInTheDocument()
        expect(useRetentionPoliciesMock).not.toHaveBeenCalled()
        expect(useLegalHoldsMock).not.toHaveBeenCalled()
    })

    it("shows a load error instead of editable default rows", () => {
        useRetentionPoliciesMock.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, "Internal Server Error", "boom"),
            isFetching: false,
            refetch: vi.fn(),
        })

        render(<ComplianceSettingsPage />)

        expect(screen.getByText("Couldn't load retention policies")).toBeInTheDocument()
        expect(screen.queryByRole("switch", { name: /retention active/ })).not.toBeInTheDocument()
        expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument()
    })

    it("shows 0 days as Keep forever and requires 1 or more days to purge", async () => {
        render(<ComplianceSettingsPage />)

        const matches = await screen.findByRole("combobox", { name: "Matches retention" })
        expect(matches).toHaveTextContent("Keep forever")
        expect(screen.queryByRole("spinbutton", { name: "Matches retention days" })).not.toBeInTheDocument()

        const donorDays = screen.getByRole("spinbutton", { name: "Donors (archived only) retention days" })
        fireEvent.change(donorDays, { target: { value: "-5" } })

        expect(donorDays).toHaveAttribute("aria-invalid", "true")
        expect(screen.getByText("Enter 1 or more days.")).toBeInTheDocument()
        const bar = screen.getByRole("region", { name: "Unsaved changes" })
        expect(within(bar).getByRole("button", { name: "Save changes" })).toBeDisabled()
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument()
    })

    it("saves changed rows from one save bar", async () => {
        render(<ComplianceSettingsPage />)

        fireEvent.change(
            await screen.findByRole("spinbutton", { name: "Donors (archived only) retention days" }),
            { target: { value: "60" } },
        )
        fireEvent.click(screen.getByRole("switch", { name: "Tasks (completed only) retention active" }))

        const bar = screen.getByRole("region", { name: "Unsaved changes" })
        expect(within(bar).getByText("2 unsaved changes")).toBeInTheDocument()
        fireEvent.click(within(bar).getByRole("button", { name: "Save changes" }))

        await waitFor(() => expect(upsertPolicyMock).toHaveBeenCalledTimes(2))
        expect(upsertPolicyMock).toHaveBeenCalledWith({ entity_type: "donors", retention_days: 60, is_active: true })
        expect(upsertPolicyMock).toHaveBeenCalledWith({ entity_type: "tasks", retention_days: 45, is_active: false })
        await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("Retention policies saved"))
    })

    it("shows a permission toast, not the server detail, when saving returns 403", async () => {
        upsertPolicyMock.mockRejectedValue(new ApiError(403, "Forbidden", "Missing permission: manage_compliance"))
        render(<ComplianceSettingsPage />)

        fireEvent.change(
            await screen.findByRole("spinbutton", { name: "Donors (archived only) retention days" }),
            { target: { value: "60" } },
        )
        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))

        await waitFor(() =>
            expect(toastError).toHaveBeenCalledWith("You don't have permission to change compliance settings.")
        )
        expect(toastError).not.toHaveBeenCalledWith(expect.stringContaining("Missing permission"))
        expect(screen.getByRole("region", { name: "Unsaved changes" })).toBeInTheDocument()
    })

    it("confirms before executing a purge", async () => {
        mockRole = "developer"
        executePurgeMock.mockResolvedValue({ job_id: "job-1" })
        render(<ComplianceSettingsPage />)

        fireEvent.click(await screen.findByRole("button", { name: "Execute Purge" }))
        const dialog = await screen.findByRole("alertdialog")
        expect(executePurgeMock).not.toHaveBeenCalled()
        fireEvent.click(within(dialog).getByRole("button", { name: "Execute purge" }))

        await waitFor(() => expect(executePurgeMock).toHaveBeenCalledTimes(1))
        await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("Purge job scheduled"))
    })

    it("validates a record ID for scopes without search", async () => {
        render(<ComplianceSettingsPage />)

        fireEvent.click(await screen.findByRole("combobox", { name: "Hold Scope" }))
        const taskOption = await screen.findByRole("option", { name: "Task" })
        fireEvent.mouseMove(taskOption)
        fireEvent.click(taskOption)
        fireEvent.change(await screen.findByLabelText("Record ID"), { target: { value: "not-a-uuid" } })
        fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Litigation" } })

        expect(screen.getByText("Enter a record ID in UUID format.")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Create Hold" })).toBeDisabled()
    })
})
