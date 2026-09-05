import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { DonorOwnershipSection } from "@/components/donors/DonorOwnershipSection"
import type { Donor } from "@/lib/types/donor"

const mocks = vi.hoisted(() => ({ options: vi.fn(), update: vi.fn(), success: vi.fn(), error: vi.fn() }))
vi.mock("@/lib/hooks/use-donors", () => ({ useDonorOwnerOptions: mocks.options, useUpdateDonor: () => ({ mutateAsync: mocks.update, isPending: false }) }))
vi.mock("@/components/ui/toast", () => ({ toast: { success: mocks.success, error: mocks.error } }))
const donor = { id: "donor-1", owner_type: "user", owner_id: "user-1", is_archived: false } as Donor
const options = { users: [{ id: "user-1", display_name: "Alex" }, { id: "user-2", display_name: "Sam" }], queues: [{ id: "queue-1", name: "Donor Intake" }] }

describe("DonorOwnershipSection", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.options.mockReturnValue({ data: options, isLoading: false, isError: false })
        mocks.update.mockResolvedValue({})
    })

    it("displays owner names and updates both owner fields for a queue", async () => {
        render(<DonorOwnershipSection donor={donor} canEdit />)
        expect(screen.getByText("Alex")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Change Owner" }))
        expect(screen.getByRole("combobox", { name: "Owner" })).toHaveTextContent("Alex")
        fireEvent.click(screen.getByRole("combobox", { name: "Owner" }))
        fireEvent.mouseMove(await screen.findByRole("option", { name: "Donor Intake" }))
        fireEvent.click(screen.getByRole("option", { name: "Donor Intake" }))
        expect(screen.getByRole("combobox", { name: "Owner" })).toHaveTextContent("Donor Intake")
        fireEvent.click(screen.getByRole("button", { name: "Save Owner" }))
        await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ id: donor.id, data: { owner_type: "queue", owner_id: "queue-1" } }))
    })

    it("assigns a member and unassigns using the paired owner contract", async () => {
        const { unmount } = render(<DonorOwnershipSection donor={donor} canEdit />)
        fireEvent.click(screen.getByRole("button", { name: "Change Owner" }))
        fireEvent.click(screen.getByRole("combobox", { name: "Owner" }))
        fireEvent.mouseMove(await screen.findByRole("option", { name: "Sam" }))
        fireEvent.click(screen.getByRole("option", { name: "Sam" }))
        fireEvent.click(screen.getByRole("button", { name: "Save Owner" }))
        await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ id: donor.id, data: { owner_type: "user", owner_id: "user-2" } }))
        unmount()
        render(<DonorOwnershipSection donor={donor} canEdit />)
        fireEvent.click(screen.getByRole("button", { name: "Change Owner" }))
        fireEvent.click(screen.getByRole("combobox", { name: "Owner" }))
        fireEvent.mouseMove(await screen.findByRole("option", { name: "Unassigned" }))
        fireEvent.click(screen.getByRole("option", { name: "Unassigned" }))
        fireEvent.click(screen.getByRole("button", { name: "Save Owner" }))
        await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ id: donor.id, data: { owner_type: null, owner_id: null } }))
    })

    it("keeps an unknown current owner labeled without exposing its id", () => {
        render(<DonorOwnershipSection donor={{ ...donor, owner_id: "removed-user" }} canEdit />)
        expect(screen.getByText("Assigned user")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Change Owner" }))
        expect(screen.getByRole("combobox", { name: "Owner" })).toHaveTextContent("Assigned user")
        expect(screen.getByRole("button", { name: "Save Owner" })).toBeDisabled()
        expect(screen.queryByText("removed-user")).not.toBeInTheDocument()
    })

    it("renders loading and retryable failure, and blocks saving without options", () => {
        mocks.options.mockReturnValue({ isLoading: true })
        const { rerender } = render(<DonorOwnershipSection donor={donor} canEdit />)
        fireEvent.click(screen.getByRole("button", { name: "Change Owner" }))
        expect(screen.getByRole("status")).toHaveTextContent("Loading owners")
        expect(screen.getByRole("button", { name: "Save Owner" })).toBeDisabled()
        const retry = vi.fn()
        mocks.options.mockReturnValue({ isError: true, refetch: retry })
        rerender(<DonorOwnershipSection donor={donor} canEdit />)
        fireEvent.click(screen.getByRole("button", { name: "Retry owners" }))
        expect(retry).toHaveBeenCalledOnce()
    })

    it("keeps the editor open when saving fails", async () => {
        mocks.update.mockRejectedValueOnce(new Error("Owner is unavailable"))
        render(<DonorOwnershipSection donor={donor} canEdit />)
        fireEvent.click(screen.getByRole("button", { name: "Change Owner" }))
        fireEvent.click(screen.getByRole("combobox", { name: "Owner" }))
        fireEvent.mouseMove(await screen.findByRole("option", { name: "Sam" }))
        fireEvent.click(screen.getByRole("option", { name: "Sam" }))
        fireEvent.click(screen.getByRole("button", { name: "Save Owner" }))
        await waitFor(() => expect(mocks.error).toHaveBeenCalledWith("Owner is unavailable"))
        expect(screen.getByRole("dialog")).toBeInTheDocument()
    })

    it("hides mutations without edit permission or when archived", () => {
        const { rerender } = render(<DonorOwnershipSection donor={donor} canEdit={false} />)
        expect(mocks.options).toHaveBeenLastCalledWith(false)
        expect(screen.queryByRole("button", { name: "Change Owner" })).not.toBeInTheDocument()
        rerender(<DonorOwnershipSection donor={{ ...donor, is_archived: true }} canEdit />)
        expect(screen.queryByRole("button", { name: "Change Owner" })).not.toBeInTheDocument()
    })
})
