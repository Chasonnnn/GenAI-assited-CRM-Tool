import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import SurrogateEmailsPage from "@/app/(app)/surrogates/[id]/emails/page"

const mocks = vi.hoisted(() => ({ permissions: vi.fn(), create: vi.fn(), deactivate: vi.fn() }))
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "surrogate-1" }) }))
vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({ useSurrogateDetailData: () => ({ effectivePermissions: mocks.permissions() }) }))
vi.mock("@/lib/hooks/use-surrogate-emails", () => ({
    useSurrogateEmails: () => ({ data: { items: [] }, isLoading: false }),
    useSurrogateEmailContacts: () => ({ data: { items: [{ id: "contact-1", email: "contact@example.test", source: "manual", is_active: true }] }, isLoading: false }),
    useCreateSurrogateEmailContact: () => ({ mutateAsync: mocks.create, isPending: false }),
    useDeactivateSurrogateEmailContact: () => ({ mutateAsync: mocks.deactivate, isPending: false }),
}))

describe("surrogate email contact permissions", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.permissions.mockReturnValue({ policy_version: 2, permissions: ["view_surrogates", "view_tickets"] })
    })

    it("keeps contact data visible without writable controls for v2 readers", () => {
        render(<SurrogateEmailsPage />)
        expect(screen.getByText("contact@example.test")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Add Contact" })).toBeDisabled()
        expect(screen.getByRole("button", { name: "Deactivate" })).toBeDisabled()
        expect(screen.getByPlaceholderText("Email")).toBeDisabled()
        fireEvent.click(screen.getByRole("button", { name: "Deactivate" }))
        expect(mocks.deactivate).not.toHaveBeenCalled()
    })

    it("allows the delegated contact action and closes it when revoked", () => {
        mocks.permissions.mockReturnValue({ policy_version: 2, permissions: ["view_surrogates", "view_tickets", "link_ticket_surrogates"] })
        const view = render(<SurrogateEmailsPage />)
        expect(screen.getByRole("button", { name: "Add Contact" })).toBeEnabled()
        expect(screen.getByRole("button", { name: "Deactivate" })).toBeEnabled()
        mocks.permissions.mockReturnValue({ policy_version: 2, permissions: ["view_surrogates", "view_tickets"] })
        view.rerender(<SurrogateEmailsPage />)
        expect(screen.getByRole("button", { name: "Deactivate" })).toBeDisabled()
    })
})
