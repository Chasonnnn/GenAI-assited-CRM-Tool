import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"
import TicketsPage from "@/app/(app)/tickets/page"

const mockUseAuth = vi.fn()
const mockUseTickets = vi.fn()
const mockPush = vi.fn()
const mockReplace = vi.fn()
const mockCompose = vi.fn()
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
    useComposeTicket: () => ({ mutateAsync: mockCompose, isPending: false }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: vi.fn(), error: vi.fn() },
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

        expect(screen.getByRole("heading", { level: 1, name: "Tickets" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 2, name: "Permission required" })).toBeInTheDocument()
        expect(screen.getByText("Tickets are available only to developers.")).toBeInTheDocument()
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "New ticket" })).not.toBeInTheDocument()
        expect(mockUseTickets).not.toHaveBeenCalled()
    })

    it("keeps compose closed until New ticket is pressed", () => {
        render(<TicketsPage />)

        expect(screen.queryByLabelText("Subject")).not.toBeInTheDocument()
        expect(screen.getByRole("combobox", { name: "Filter by status" })).toHaveTextContent("All statuses")
        expect(screen.getByRole("combobox", { name: "Filter by priority" })).toHaveTextContent("All priorities")
        expect(screen.getByRole("textbox", { name: "Search tickets" })).toBeInTheDocument()
        expect(screen.getByText("No tickets")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "New ticket" }))

        const dialog = screen.getByRole("dialog", { name: "New ticket" })
        expect(within(dialog).getByLabelText("To")).toBeInTheDocument()
        expect(within(dialog).getByLabelText("Subject")).toBeInTheDocument()
        expect(within(dialog).getByLabelText("Message")).toBeInTheDocument()
    })

    it("shows inline errors on every empty compose field instead of sending", async () => {
        render(<TicketsPage />)
        fireEvent.click(screen.getByRole("button", { name: "New ticket" }))
        const dialog = screen.getByRole("dialog", { name: "New ticket" })

        fireEvent.click(within(dialog).getByRole("button", { name: "Send" }))

        expect(await within(dialog).findByText("Enter a recipient email.")).toBeInTheDocument()
        expect(within(dialog).getByText("Enter a subject.")).toBeInTheDocument()
        expect(within(dialog).getByText("Enter a message.")).toBeInTheDocument()
        expect(within(dialog).getByLabelText("To")).toHaveAttribute("aria-invalid", "true")
        expect(mockCompose).not.toHaveBeenCalled()

        fireEvent.change(within(dialog).getByLabelText("To"), { target: { value: "not-an-email" } })
        expect(within(dialog).getByText("Enter a valid email address.")).toBeInTheDocument()
    })

    it("sends a valid compose form and opens the new ticket", async () => {
        mockCompose.mockResolvedValue({ status: "sent", ticket_id: "ticket-9" })
        render(<TicketsPage />)
        fireEvent.click(screen.getByRole("button", { name: "New ticket" }))
        const dialog = screen.getByRole("dialog", { name: "New ticket" })

        fireEvent.change(within(dialog).getByLabelText("To"), { target: { value: " person@example.com " } })
        fireEvent.change(within(dialog).getByLabelText("Subject"), { target: { value: "Hello" } })
        fireEvent.change(within(dialog).getByLabelText("Message"), { target: { value: "Body" } })
        fireEvent.click(within(dialog).getByRole("button", { name: "Send" }))

        await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/tickets/ticket-9"))
        expect(mockCompose).toHaveBeenCalledWith({
            to_emails: ["person@example.com"],
            subject: "Hello",
            body_text: "Body",
        })
    })

    it("attaches a 422 on the recipient to the To field", async () => {
        mockCompose.mockRejectedValue(
            new ApiError(422, "Unprocessable Entity", "Validation failed", [
                { path: "to_emails.0", message: "value is not a valid email address: bad" },
            ]),
        )
        render(<TicketsPage />)
        fireEvent.click(screen.getByRole("button", { name: "New ticket" }))
        const dialog = screen.getByRole("dialog", { name: "New ticket" })

        fireEvent.change(within(dialog).getByLabelText("To"), { target: { value: "a@b.co" } })
        fireEvent.change(within(dialog).getByLabelText("Subject"), { target: { value: "Hello" } })
        fireEvent.change(within(dialog).getByLabelText("Message"), { target: { value: "Body" } })
        fireEvent.click(within(dialog).getByRole("button", { name: "Send" }))

        expect(await within(dialog).findByText("Enter a valid email address.")).toBeInTheDocument()
        expect(mockPush).not.toHaveBeenCalled()
    })

    it("offers Clear filters when a filtered search is empty", () => {
        render(<TicketsPage />)
        fireEvent.change(screen.getByRole("textbox", { name: "Search tickets" }), { target: { value: "zzz" } })

        expect(screen.getByText("No matching tickets")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }))
        expect(screen.getByText("No tickets")).toBeInTheDocument()
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
