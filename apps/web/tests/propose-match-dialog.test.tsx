import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ProposeMatchDialog } from "@/components/matches/ProposeMatchDialog"

const mockUseIntendedParents = vi.fn()
const mockUseEffectivePermissions = vi.fn()

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

vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParents: (filters: unknown, options: unknown) =>
        mockUseIntendedParents(filters, options),
}))

vi.mock("@/lib/hooks/use-matches", () => ({
    useCreateMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function renderDialog(open = true) {
    return render(
        <ProposeMatchDialog
            open={open}
            onOpenChange={vi.fn()}
            surrogateId="surrogate-1"
            surrogateName="Test Surrogate"
        />
    )
}

describe("ProposeMatchDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_intended_parents"] },
            isLoading: false,
        })
        mockUseIntendedParents.mockReturnValue({
            data: { items: [] },
            isLoading: false,
        })
    })

    it("does not fetch intended parents while the dialog is closed", () => {
        renderDialog(false)

        expect(mockUseIntendedParents).toHaveBeenCalledWith(
            { per_page: 100 },
            { enabled: false }
        )
    })

    it("does not fetch intended parents and explains missing permission", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: [] },
            isLoading: false,
        })

        renderDialog(true)

        expect(mockUseIntendedParents).toHaveBeenCalledWith(
            { per_page: 100 },
            { enabled: false }
        )
        expect(
            screen.getByText(/does not have permission to view intended parents/i)
        ).toBeInTheDocument()
    })

    it("fetches intended parents when open and permitted", () => {
        renderDialog(true)

        expect(mockUseIntendedParents).toHaveBeenCalledWith(
            { per_page: 100 },
            { enabled: true }
        )
    })
})
