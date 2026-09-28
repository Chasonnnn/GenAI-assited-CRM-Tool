import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import { EditDialog } from "@/components/surrogates/detail/SurrogateDetailLayout/dialogs/EditDialog"

const mocks = vi.hoisted(() => ({
    useAuth: vi.fn(),
    updateSurrogate: vi.fn(),
    closeDialog: vi.fn(),
}))

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ open, children }: { open?: boolean; children?: ReactNode }) => (open ? <div>{children}</div> : null),
    DialogContent: ({ children, size }: { children?: ReactNode; size?: string }) => (
        <div data-testid="dialog-content" data-size={size}>
            {children}
        </div>
    ),
    DialogHeader: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children?: ReactNode }) => <h2>{children}</h2>,
    DialogFooter: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mocks.useAuth(),
}))

vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({
    useSurrogateDetailData: () => ({
        surrogate: {
            id: "sur-1",
            surrogate_number: "S10152",
            full_name: "QA Surrogate",
            email: "qa-surrogate@example.com",
            phone: null,
            state: null,
            date_of_birth: null,
            race: null,
            height_ft: 5.5,
            weight_lb: 140,
            is_priority: false,
            eligibility_checklist: [],
        },
    }),
    useSurrogateDetailDialogs: () => ({
        activeDialog: { type: "edit_surrogate" },
        closeDialog: mocks.closeDialog,
    }),
    useSurrogateDetailActions: () => ({
        updateSurrogate: mocks.updateSurrogate,
        isUpdatePending: false,
    }),
}))

describe("EditDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.useAuth.mockReturnValue({ user: { role: "admin" } })
        mocks.updateSurrogate.mockResolvedValue(undefined)
    })

    it("renders at the 2xl size with Priority as a switch outside the eligibility checklist", () => {
        render(<EditDialog />)

        expect(screen.getByTestId("dialog-content")).toHaveAttribute("data-size", "2xl")
        expect(screen.getByRole("switch", { name: "Priority" })).not.toBeChecked()
        expect(screen.queryByText("Priority Surrogate")).not.toBeInTheDocument()
    })

    it("hides the priority switch from roles that cannot manage priority", () => {
        mocks.useAuth.mockReturnValue({ user: { role: "intake" } })
        render(<EditDialog />)

        expect(screen.queryByRole("switch", { name: "Priority" })).not.toBeInTheDocument()
    })

    it("uses one Height label over compact feet and inch selects", () => {
        render(<EditDialog />)

        expect(screen.getByText("Height")).toBeInTheDocument()
        expect(screen.queryByText("Height Feet")).not.toBeInTheDocument()
        expect(screen.queryByText("Height Inches")).not.toBeInTheDocument()
        expect(screen.getByRole("combobox", { name: "Height feet" })).toHaveTextContent("5")
        expect(screen.getByRole("combobox", { name: "Height inches" })).toHaveTextContent("6")
    })

    it("offers no ft or in placeholder rows in the height selects", async () => {
        render(<EditDialog />)

        fireEvent.click(screen.getByRole("combobox", { name: "Height feet" }))
        const listbox = await screen.findByRole("listbox")
        const options = within(listbox).getAllByRole("option").map((option) => option.textContent)
        expect(options).toContain("Not provided")
        expect(options).not.toContain("ft")
        expect(options).toContain("5")
    })

    it("shows the empty-value token, not a value label, for an empty race", () => {
        render(<EditDialog />)

        const race = screen.getByRole("combobox", { name: "Race" })
        expect(race).toHaveTextContent("—")
        expect(race).not.toHaveTextContent("Not provided")
    })

    it("saves the priority switch and the height", async () => {
        render(<EditDialog />)

        fireEvent.click(screen.getByRole("switch", { name: "Priority" }))
        fireEvent.click(screen.getByRole("button", { name: "Save Changes" }))

        await waitFor(() => expect(mocks.updateSurrogate).toHaveBeenCalledTimes(1))
        expect(mocks.updateSurrogate.mock.calls[0]?.[0]).toMatchObject({
            is_priority: true,
            height_ft: 5.5,
            race: null,
        })
    })
})
