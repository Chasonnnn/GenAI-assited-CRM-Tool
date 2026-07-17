import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import TicketDetailPage from "@/app/(app)/tickets/[ticketId]/page"

const mockUseTicket = vi.fn()

vi.mock("next/navigation", () => ({
    useParams: () => ({ ticketId: "ticket-1" }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { role: "developer" } }),
}))

vi.mock("@/lib/hooks/use-tickets", () => ({
    useTicket: () => mockUseTicket(),
    usePatchTicket: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useReplyTicket: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useAddTicketNote: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useLinkTicketSurrogate: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe("TicketDetailPage", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("preserves a recipient edit when equivalent ticket data rerenders", () => {
        const ticket = {
            id: "ticket-1",
            ticket_code: "T-1001",
            subject: "Help requested",
            requester_email: "original@example.com",
            status: "open",
            priority: "normal",
            surrogate_id: null,
            surrogate_link_status: null,
        }
        let queryResult = {
            data: { ticket, notes: [], messages: [] },
            isLoading: false,
        }
        mockUseTicket.mockImplementation(() => queryResult)

        const { rerender } = render(<TicketDetailPage />)
        const recipient = screen.getByPlaceholderText("Recipient")
        fireEvent.change(recipient, { target: { value: "edited@example.com" } })
        expect(recipient).toHaveValue("edited@example.com")

        queryResult = {
            data: { ticket: { ...ticket }, notes: [], messages: [] },
            isLoading: false,
        }
        rerender(<TicketDetailPage />)

        expect(screen.getByPlaceholderText("Recipient")).toHaveValue("edited@example.com")
    })
})
