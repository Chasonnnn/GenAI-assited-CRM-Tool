import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { DonorAssignMenu } from "@/components/donors/DonorAssignMenu"
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import type { Donor } from "@/lib/types/donor"

const mocks = vi.hoisted(() => ({ options: vi.fn(), update: vi.fn(), success: vi.fn(), error: vi.fn() }))
vi.mock("@/lib/hooks/use-donors", () => ({
    useDonorOwnerOptions: mocks.options,
    useUpdateDonor: () => ({ mutateAsync: mocks.update, isPending: false }),
}))
vi.mock("@/components/ui/toast", () => ({ toast: { success: mocks.success, error: mocks.error } }))
const donor = { id: "donor-1", owner_type: "user", owner_id: "user-1" } as Donor
const options = {
    users: [{ id: "user-1", display_name: "Alex" }, { id: "user-2", display_name: "Sam" }],
    queues: [{ id: "queue-1", name: "Donor Intake" }],
}

function openAssignment(record = donor) {
    render(<DropdownMenu defaultOpen>
        <DropdownMenuTrigger>Actions</DropdownMenuTrigger>
        <DropdownMenuContent><DonorAssignMenu donor={record} /></DropdownMenuContent>
    </DropdownMenu>)
    fireEvent.keyDown(screen.getByRole("menuitem", { name: "Assign" }), { key: "ArrowRight" })
}

describe("DonorAssignMenu", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.options.mockReturnValue({ data: options, isLoading: false, isError: false })
        mocks.update.mockResolvedValue({})
    })

    it.each([
        ["Sam", "user", "user-2"],
        ["Donor Intake", "queue", "queue-1"],
        ["Unassign", null, null],
    ])("assigns %s using the paired owner contract", async (label, ownerType, ownerId) => {
        openAssignment()
        expect(await screen.findByRole("menuitem", { name: "Alex" })).toHaveAttribute("aria-disabled", "true")
        fireEvent.click(screen.getByRole("menuitem", { name: label! }))
        await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
            id: "donor-1", data: { owner_type: ownerType, owner_id: ownerId },
        }))
    })

    it("shows names rather than stored IDs when the current owner is unavailable", async () => {
        openAssignment({ ...donor, owner_id: "removed-user" })
        expect(await screen.findByRole("menuitem", { name: "Sam" })).toBeInTheDocument()
        expect(screen.queryByText(/removed-user|user-2|queue-1/)).not.toBeInTheDocument()
        expect(screen.getByRole("menuitem", { name: "Unassign" })).not.toHaveAttribute("aria-disabled", "true")
    })

    it.each(["loading", "error"])("does not offer assignment while options are %s", async (state) => {
        const retry = vi.fn()
        mocks.options.mockReturnValue({ isLoading: state === "loading", isError: state === "error", refetch: retry })
        openAssignment()
        const item = await screen.findByRole("menuitem", { name: state === "loading" ? "Loading…" : "Retry owners" })
        expect(screen.queryByRole("menuitem", { name: "Unassign" })).not.toBeInTheDocument()
        if (state === "loading") expect(item).toHaveAttribute("aria-disabled", "true")
        else {
            fireEvent.click(item)
            expect(retry).toHaveBeenCalledOnce()
        }
        expect(mocks.update).not.toHaveBeenCalled()
    })

    it("reports an assignment failure without a success notification", async () => {
        mocks.update.mockRejectedValueOnce(new Error("Owner unavailable"))
        openAssignment()
        fireEvent.click(await screen.findByRole("menuitem", { name: "Sam" }))
        await waitFor(() => expect(mocks.error).toHaveBeenCalledWith("Unable to update assignment"))
        expect(mocks.success).not.toHaveBeenCalled()
    })
})
