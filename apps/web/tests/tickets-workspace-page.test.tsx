import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import TicketsPage from "@/app/(app)/tickets/page"

const mockUseAuth = vi.fn()
const mockUseTickets = vi.fn()
const mockPush = vi.fn()
const mockReplace = vi.fn()
const mockSearchState = vi.hoisted(() => ({ view: null as string | null }))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush, replace: mockReplace }),
    useSearchParams: () => ({
        get: (key: string) => key === "view" ? mockSearchState.view : null,
    }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-tickets", () => ({
    useTickets: (...args: unknown[]) => mockUseTickets(...args),
    useComposeTicket: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/app/(app)/messages/page.client", () => ({
    default: () => <div>SMS inbox content</div>,
}))

describe("TicketsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSearchState.view = null
        mockUseAuth.mockReturnValue({
            user: { user_id: "developer-1", role: "developer" },
            isLoading: false,
        })
        mockUseTickets.mockReturnValue({
            data: { items: [], next_cursor: null },
            isLoading: false,
        })
    })

    it("blocks non-developers before requesting ticket data", () => {
        mockUseAuth.mockReturnValue({
            user: { user_id: "admin-1", role: "admin" },
            isLoading: false,
        })

        render(<TicketsPage />)

        expect(screen.getByText("Tickets are available only to developers.")).toBeInTheDocument()
        expect(mockUseTickets).not.toHaveBeenCalled()
    })

    it("combines email tickets and SMS/MMS under one ticket workspace", () => {
        render(<TicketsPage />)

        expect(screen.getByRole("heading", { name: "Tickets" })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: "Email tickets" })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: "SMS/MMS" })).toBeInTheDocument()
        expect(mockUseTickets).toHaveBeenCalledWith(expect.any(Object))

        fireEvent.click(screen.getByRole("tab", { name: "SMS/MMS" }))
        expect(mockReplace).toHaveBeenCalledWith(
            "/tickets?view=messages",
            { scroll: false },
        )
    })

    it("renders the SMS/MMS inbox without mounting the email ticket list", () => {
        mockSearchState.view = "messages"

        render(<TicketsPage />)

        expect(screen.getByText("SMS inbox content")).toBeInTheDocument()
        expect(mockUseTickets).not.toHaveBeenCalled()
    })
})
