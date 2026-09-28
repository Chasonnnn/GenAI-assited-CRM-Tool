import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"

import { DonorApplicationsSection } from "@/components/donors/DonorApplicationsSection"

const mockUseDonorSubmissions = vi.fn()

vi.mock("@/lib/hooks/use-forms", () => ({
    useDonorSubmissions: (donorId: string | null) => mockUseDonorSubmissions(donorId),
}))

describe("DonorApplicationsSection", () => {
    beforeEach(() => {
        mockUseDonorSubmissions.mockReset()
    })

    it("renders a loading state", () => {
        mockUseDonorSubmissions.mockReturnValue({ data: undefined, isLoading: true, isError: false })
        render(<DonorApplicationsSection donorId="donor-1" canOpenSubmissions />)
        expect(screen.getByRole("status", { name: "Loading applications" })).toBeInTheDocument()
        expect(screen.queryByRole("table")).not.toBeInTheDocument()
    })

    it("renders a retryable error state", () => {
        const refetch = vi.fn()
        mockUseDonorSubmissions.mockReturnValue({ data: undefined, isLoading: false, isError: true, isFetching: false, refetch })
        render(<DonorApplicationsSection donorId="donor-1" canOpenSubmissions />)
        expect(screen.getByText("Couldn't load applications")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it("renders an empty state", () => {
        mockUseDonorSubmissions.mockReturnValue({ data: [], isLoading: false, isError: false })
        render(<DonorApplicationsSection donorId="donor-1" canOpenSubmissions />)
        expect(screen.getByText("No applications")).toBeInTheDocument()
    })

    it("lists each application with its date, form, and readable status", () => {
        mockUseDonorSubmissions.mockReturnValue({
            data: [
                { id: "s-1", form_id: "form-1", form_name: "Egg donor application", status: "approved", submitted_at: "2026-09-01T15:00:00Z", reviewed_at: null },
                { id: "s-2", form_id: "form-2", form_name: "Photo update", status: "pending_review", submitted_at: "2026-09-20T15:00:00Z", reviewed_at: null },
                { id: "s-3", form_id: "form-3", form_name: "Medical history", status: "rejected", submitted_at: "2026-09-21T15:00:00Z", reviewed_at: null },
            ],
            isLoading: false,
            isError: false,
        })
        render(<DonorApplicationsSection donorId="donor-1" canOpenSubmissions />)
        expect(mockUseDonorSubmissions).toHaveBeenCalledWith("donor-1")
        const rows = within(screen.getByRole("table", { name: "Donor applications" })).getAllByRole("row")
        expect(rows).toHaveLength(4)
        expect(within(rows[1]!).getByText(new Date("2026-09-01T15:00:00Z").toLocaleString())).toBeInTheDocument()
        expect(within(rows[1]!).getByRole("link", { name: "Egg donor application" })).toHaveAttribute(
            "href",
            "/automation/form-submissions?form=form-1",
        )
        expect(within(rows[1]!).getByText("Approved")).toBeInTheDocument()
        expect(within(rows[2]!).getByText("Pending Review")).toBeInTheDocument()
        expect(within(rows[3]!).getByText("Rejected")).toBeInTheDocument()
        expect(screen.queryByText("pending_review")).not.toBeInTheDocument()
    })
})
