import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { RecordCollaboratorsDialog } from "@/components/permissions/record-collaborators-dialog"
import * as api from "@/lib/api/record-scopes"

vi.mock("@/lib/api/record-scopes", async (original) => ({ ...await original<typeof api>(), getCollaborators: vi.fn(), getCollaboratorOptions: vi.fn(), addCollaborator: vi.fn(), removeCollaborator: vi.fn() }))

const props = { kind: "donor" as const, recordId: "donor-1", open: true, onOpenChange: vi.fn(), canManage: true }
const existing = { id: "grant-1", user_id: "staff-1", donor_id: "donor-1", surrogate_id: null, display_name: "Taylor Morgan" }

describe("record collaborators", () => {
    beforeEach(() => {
        vi.mocked(api.getCollaborators).mockReset().mockResolvedValue([])
        vi.mocked(api.getCollaboratorOptions).mockReset().mockResolvedValue([{ user_id: "staff-1", display_name: "Taylor Morgan" }])
        vi.mocked(api.addCollaborator).mockReset().mockResolvedValue(existing)
        vi.mocked(api.removeCollaborator).mockReset().mockResolvedValue(undefined)
    })

    it("adds an explicit record grant and displays the staff name", async () => {
        render(<RecordCollaboratorsDialog {...props} />)
        expect(await screen.findByText("No collaborators.")).toBeVisible()
        fireEvent.click(await screen.findByRole("combobox", { name: "Team member" }))
        fireEvent.click(await screen.findByRole("option", { name: "Taylor Morgan" }))
        expect(screen.getByRole("combobox", { name: "Team member" })).toHaveTextContent("Taylor Morgan")
        vi.mocked(api.getCollaborators).mockResolvedValue([existing])
        fireEvent.click(screen.getByRole("button", { name: "Add", exact: true }))
        await waitFor(() => expect(api.addCollaborator).toHaveBeenCalledWith("donor", "donor-1", "staff-1"))
        expect(await screen.findByRole("button", { name: "Remove Taylor Morgan" })).toBeVisible()
        expect(screen.getByRole("button", { name: "Add", exact: true })).toBeDisabled()
    })

    it("removes existing grants even when the recipient is absent from active options", async () => {
        vi.mocked(api.getCollaborators).mockResolvedValue([existing])
        vi.mocked(api.getCollaboratorOptions).mockResolvedValue([])
        render(<RecordCollaboratorsDialog {...props} />)
        const remove = await screen.findByRole("button", { name: "Remove Taylor Morgan" })
        vi.mocked(api.getCollaborators).mockResolvedValue([])
        fireEvent.click(remove)
        await waitFor(() => expect(api.removeCollaborator).toHaveBeenCalledWith("donor", "donor-1", "staff-1"))
        expect(await screen.findByText("No collaborators.")).toBeVisible()
    })

    it("keeps failed removal visible for correction", async () => {
        vi.mocked(api.getCollaborators).mockResolvedValue([existing])
        vi.mocked(api.removeCollaborator).mockRejectedValue(new Error("Access changed"))
        render(<RecordCollaboratorsDialog {...props} />)
        fireEvent.click(await screen.findByRole("button", { name: "Remove Taylor Morgan" }))
        expect(await screen.findByRole("alert")).toHaveTextContent("Access changed")
        expect(screen.getByRole("button", { name: "Remove Taylor Morgan" })).toBeVisible()
    })

    it("does not fetch staff or show controls without administration capability", () => {
        render(<RecordCollaboratorsDialog {...props} canManage={false} />)
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
        expect(api.getCollaborators).not.toHaveBeenCalled()
        expect(api.getCollaboratorOptions).not.toHaveBeenCalled()
    })
})
