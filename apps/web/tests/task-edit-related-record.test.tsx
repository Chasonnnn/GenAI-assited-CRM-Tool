import type { ReactNode } from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const recordMocks = vi.hoisted(() => ({
    donors: vi.fn(),
    surrogates: vi.fn(),
    intendedParents: vi.fn(),
    permissions: ["view_surrogates", "view_intended_parents", "view_donors"] as string[] | undefined,
}))

vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { user_id: "user-1" } }) }))
vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({
        data: recordMocks.permissions ? { permissions: recordMocks.permissions } : undefined,
    }),
}))

vi.mock("@/lib/hooks/use-donors", () => ({
    useDonors: (params: unknown, options: unknown) => recordMocks.donors(params, options),
}))
vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSurrogates: (params: unknown, options: unknown) => recordMocks.surrogates(params, options),
}))
vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParents: (params: unknown, options: unknown) => recordMocks.intendedParents(params, options),
}))

vi.mock("@/components/ui/select", () => ({
    Select: ({ value, onValueChange, children }: {
        value?: string
        onValueChange: (value: string) => void
        children: ReactNode
    }) => (
        <select value={value ?? ""} onChange={(event) => onValueChange(event.target.value)}>
            {children}
        </select>
    ),
    SelectTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectValue: () => null,
    SelectContent: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectItem: ({ value, children }: { value: string; children: ReactNode }) => (
        <option value={value}>{children}</option>
    ),
}))

import { TaskEditModal } from "@/components/tasks/TaskEditModal"

const page = (items: unknown[] = []) => ({ data: { items }, isLoading: false, isError: false })

describe("TaskEditModal related record", () => {
    beforeEach(() => {
        recordMocks.donors.mockReset().mockReturnValue(page())
        recordMocks.surrogates.mockReset().mockReturnValue(page())
        recordMocks.intendedParents.mockReset().mockReturnValue(page())
        recordMocks.permissions = ["view_surrogates", "view_intended_parents", "view_donors"]
    })

    it("leaves out record types the role cannot view instead of requesting them", () => {
        recordMocks.permissions = ["view_surrogates", "view_donors"]
        render(<TaskEditModal open onClose={vi.fn()} onSave={vi.fn()} task={{ id: "task-1", title: "Review", description: null, task_type: "review", due_date: null, due_time: null, is_completed: false, surrogate_id: null }} />)

        fireEvent.click(screen.getByRole("button", { name: /^Linked record/ }))
        const recordType = screen.getByRole("group", { name: "Record type" })
        expect(within(recordType).getByRole("button", { name: "Surrogates" })).toBeInTheDocument()
        expect(within(recordType).getByRole("button", { name: "Donors" })).toBeInTheDocument()
        expect(within(recordType).queryByRole("button", { name: "Intended Parents" })).not.toBeInTheDocument()
        expect(recordMocks.surrogates).toHaveBeenLastCalledWith(expect.anything(), { enabled: true })
        expect(recordMocks.intendedParents).toHaveBeenLastCalledWith(expect.anything(), { enabled: false })
    })

    it("offers every record type while the permission lookup is unavailable", () => {
        recordMocks.permissions = undefined
        render(<TaskEditModal open onClose={vi.fn()} onSave={vi.fn()} task={{ id: "task-1", title: "Review", description: null, task_type: "review", due_date: null, due_time: null, is_completed: false, surrogate_id: null }} />)

        fireEvent.click(screen.getByRole("button", { name: /^Linked record/ }))
        expect(within(screen.getByRole("group", { name: "Record type" })).getByRole("button", { name: "Intended Parents" })).toBeInTheDocument()
        expect(recordMocks.intendedParents).toHaveBeenLastCalledWith(expect.anything(), { enabled: true })
    })

    it("preserves edited values and shows a failed save", async () => {
        const onClose = vi.fn()
        render(<TaskEditModal open onClose={onClose} onSave={vi.fn().mockRejectedValue(new Error("Save failed"))} task={{ id: "task-1", title: "Review", description: null, task_type: "review", due_date: null, due_time: null, is_completed: false, surrogate_id: null }} />)
        fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Updated review" } })
        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Save failed"))
        expect(screen.getByLabelText("Title")).toHaveValue("Updated review")
        expect(onClose).not.toHaveBeenCalled()
    })

    it("keeps Delete apart from Save and confirms with a red destructive button", async () => {
        const onClose = vi.fn()
        const onDelete = vi.fn().mockRejectedValueOnce(new Error("Delete failed")).mockResolvedValueOnce(undefined)
        render(<TaskEditModal open onClose={onClose} onSave={vi.fn()} onDelete={onDelete} task={{ id: "task-1", title: "Review", description: null, task_type: "review", due_date: null, due_time: null, is_completed: false, surrogate_id: null }} />)
        const deleteButton = screen.getByRole("button", { name: "Delete task" })
        expect(deleteButton.closest('[data-slot="dialog-footer-start"]')).not.toBeNull()
        expect(deleteButton).toHaveClass("text-destructive")
        expect(screen.getByRole("button", { name: "Save changes" }).closest('[data-slot="dialog-footer-start"]')).toBeNull()

        fireEvent.click(deleteButton)
        const dialog = screen.getByRole("alertdialog")
        expect(within(dialog).getByRole("heading", { name: "Delete task?" })).toBeInTheDocument()
        const confirm = within(dialog).getByRole("button", { name: "Delete task" })
        expect(confirm).toHaveClass("bg-destructive")
        expect(confirm.className).not.toMatch(/linear-gradient/)
        fireEvent.click(confirm)
        await waitFor(() => expect(within(dialog).getByRole("alert")).toHaveTextContent("Delete failed"))
        expect(onClose).not.toHaveBeenCalled()
        fireEvent.click(within(dialog).getByRole("button", { name: "Delete task" }))
        await waitFor(() => expect(onClose).toHaveBeenCalledOnce())
    })

    it("searches every record type on the server and shows name and number per option", async () => {
        recordMocks.surrogates.mockImplementation((params: { q?: string }) => page(
            params.q === "soph" ? [{ id: "s-151", full_name: "Sophia Gonzalez", surrogate_number: "S10151" }] : [],
        ))
        recordMocks.intendedParents.mockImplementation((params: { q?: string }) => page(
            params.q === "soph" ? [{ id: "ip-9", full_name: "Sophia & Daniel Reed", intended_parent_number: "I10009" }] : [],
        ))
        const onSave = vi.fn().mockResolvedValue(undefined)
        render(<TaskEditModal open onClose={vi.fn()} onSave={onSave} task={{ id: "task-1", title: "Review", description: null, task_type: "review", due_date: null, due_time: null, is_completed: false, surrogate_id: null }} />)

        // Records load only once the picker opens.
        expect(recordMocks.surrogates).toHaveBeenLastCalledWith(expect.anything(), { enabled: false })
        fireEvent.click(screen.getByRole("button", { name: /^Linked record/ }))
        expect(recordMocks.surrogates).toHaveBeenLastCalledWith({ per_page: 20, include_archived: false }, { enabled: true })

        fireEvent.change(screen.getByRole("combobox", { name: "Search records" }), { target: { value: "soph" } })
        await waitFor(() => expect(recordMocks.surrogates).toHaveBeenLastCalledWith(
            { per_page: 20, include_archived: false, q: "soph" },
            { enabled: true },
        ))
        expect(recordMocks.donors).toHaveBeenLastCalledWith({ donor_type: "sperm", per_page: 20, q: "soph" }, { enabled: true })
        expect(await screen.findByText("Surrogates", { selector: "[data-slot=command-group-heading]" })).toBeInTheDocument()
        expect(screen.getByText("Intended Parents", { selector: "[data-slot=command-group-heading]" })).toBeInTheDocument()
        expect(screen.getByRole("option", { name: "Sophia Gonzalez S10151" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Intended Parents" }))
        expect(recordMocks.surrogates).toHaveBeenLastCalledWith(expect.anything(), { enabled: false })
        expect(screen.queryByRole("option", { name: "Sophia Gonzalez S10151" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("option", { name: "Sophia & Daniel Reed I10009" }))
        expect(screen.getByRole("button", { name: /^Linked record/ })).toHaveTextContent("Intended Parent I10009 — Sophia & Daniel Reed")
        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))
        await waitFor(() => expect(onSave).toHaveBeenCalledWith("task-1", expect.objectContaining({
            intended_parent_id: "ip-9",
            surrogate_id: null,
            donor_id: null,
        })))
    })

    it("preselects a donor and sends explicit nulls when the link is removed", async () => {
        const onSave = vi.fn().mockResolvedValue(undefined)
        render(
            <TaskEditModal
                open
                onClose={vi.fn()}
                onSave={onSave}
                task={{
                    id: "task-1",
                    title: "Review profile",
                    description: null,
                    task_type: "review",
                    due_date: null,
                    due_time: null,
                    is_completed: false,
                    surrogate_id: null,
                    intended_parent_id: null,
                    donor_id: "donor-1",
                    donor_number: "D10001",
                    donor_type: "egg",
                    donor_name: "Maya Thompson",
                }}
            />,
        )

        const linkedRecord = screen.getByRole("button", { name: /^Linked record/ })
        expect(linkedRecord).toHaveTextContent("Egg Donor D10001")

        fireEvent.click(linkedRecord)
        fireEvent.click(await screen.findByRole("option", { name: "No linked record" }))
        expect(linkedRecord).toHaveTextContent("No linked record")
        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))

        await waitFor(() => expect(onSave).toHaveBeenCalledWith(
            "task-1",
            expect.objectContaining({
                surrogate_id: null,
                intended_parent_id: null,
                donor_id: null,
            }),
        ))
    })
})
