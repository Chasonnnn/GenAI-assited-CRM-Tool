import { fireEvent, render, screen, waitFor } from "@testing-library/react"
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

    it("focuses the intended parent picker on open and has no title icon", async () => {
        renderDialog(true)

        const picker = screen.getByRole("button", { name: /intended parent\(s\)/i })
        await waitFor(() => expect(picker).toHaveFocus())
        expect(screen.getByRole("dialog").querySelector("h2 svg")).toBeNull()
        expect(screen.getByRole("textbox", { name: /notes/i })).not.toHaveFocus()
    })

    it("focuses the picker even while the intended parent list is loading", async () => {
        mockUseIntendedParents.mockReturnValue({ data: undefined, isLoading: true })
        renderDialog(true)

        const picker = screen.getByRole("button", { name: /intended parent\(s\)/i })
        await waitFor(() => expect(picker).toHaveFocus())

        fireEvent.click(picker)
        expect(await screen.findByRole("status")).toHaveTextContent("Loading…")
    })

    it("filters intended parents by typed text and selects one", async () => {
        mockUseIntendedParents.mockReturnValue({
            data: {
                items: [
                    { id: "ip-1", full_name: "Jordan Lee", email: "jordan@example.com", intended_parent_number: "I10001" },
                    { id: "ip-2", full_name: "Morgan Diaz", email: "morgan@example.com", intended_parent_number: "I10002" },
                ],
            },
            isLoading: false,
        })
        renderDialog(true)

        fireEvent.click(screen.getByRole("button", { name: /intended parent\(s\)/i }))
        const search = await screen.findByRole("combobox", { name: "Search intended parents" })
        fireEvent.change(search, { target: { value: "morg" } })

        expect(screen.queryByText("Jordan Lee")).not.toBeInTheDocument()
        fireEvent.click(screen.getByText("Morgan Diaz"))

        await waitFor(() =>
            expect(screen.queryByRole("combobox", { name: "Search intended parents" })).not.toBeInTheDocument(),
        )
        const picker = document.getElementById("ip-select")
        expect(picker).toHaveTextContent("Morgan Diaz")
        expect(picker).toHaveAttribute("aria-labelledby", "ip-select-label ip-select")
        expect(screen.getByText("Propose Match", { selector: "button" })).toBeEnabled()
    })
})
