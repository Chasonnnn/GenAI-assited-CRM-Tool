import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"
import TicketDetailPage from "@/app/(app)/tickets/[ticketId]/page"

const mockUseTicket = vi.fn()
const authState = vi.hoisted(() => ({ role: "developer" }))

vi.mock("next/navigation", () => ({
    useParams: () => ({ ticketId: "ticket-1" }),
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { role: authState.role } }),
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
        authState.role = "developer"
    })

    it("shows the permission-denied state to non-developers", () => {
        authState.role = "admin"
        mockUseTicket.mockReturnValue({ data: undefined, isLoading: false, isError: false })

        render(<TicketDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Permission required" })).toBeInTheDocument()
        expect(screen.getByText("Tickets are available only to developers.")).toBeInTheDocument()
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    })

    it("shows Ticket not found with a way back for a 404", () => {
        mockUseTicket.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new ApiError(404, "Not Found", "Ticket not found"),
            refetch: vi.fn(),
        })

        render(<TicketDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Ticket not found" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Tickets" })).toHaveAttribute("href", "/tickets")
    })

    it("treats a malformed ticket id (422) as not found", () => {
        mockUseTicket.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new ApiError(422, "Unprocessable Entity", "ticket_id: Input should be a valid UUID"),
            refetch: vi.fn(),
        })

        render(<TicketDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Ticket not found" })).toBeInTheDocument()
        expect(screen.queryByText(/valid UUID/)).not.toBeInTheDocument()
    })

    it("offers a retry for other load failures without the raw message", () => {
        const refetch = vi.fn()
        mockUseTicket.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            error: new ApiError(500, "Internal Server Error", "database exploded"),
            refetch,
        })

        render(<TicketDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Couldn't load ticket" })).toBeInTheDocument()
        expect(screen.queryByText(/database exploded/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalled()
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
