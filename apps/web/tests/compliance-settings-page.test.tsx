import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import ComplianceSettingsPage from "../app/(app)/settings/compliance/page"

const useRetentionPoliciesMock = vi.fn()
const useLegalHoldsMock = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { role: "admin" } }),
}))

vi.mock("@/lib/hooks/use-compliance", () => ({
    useRetentionPolicies: () => useRetentionPoliciesMock(),
    useUpsertRetentionPolicy: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useLegalHolds: (params: { page: number; per_page: number }) =>
        useLegalHoldsMock(params),
    useCreateLegalHold: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useReleaseLegalHold: () => ({ mutateAsync: vi.fn(), isPending: false }),
    usePurgePreview: () => ({ data: { items: [] }, refetch: vi.fn() }),
    useExecutePurge: () => ({ mutateAsync: vi.fn() }),
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
        useRetentionPoliciesMock.mockReturnValue({
            data: [policy("surrogates", 30), policy("tasks", 45)],
            isLoading: false,
        })
        useLegalHoldsMock.mockReturnValue({
            data: { items: [], total: 0, page: 1, per_page: 20, pages: 1 },
            isLoading: false,
        })
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
})
