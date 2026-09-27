import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"

const mockUseDonors = vi.fn()
const mockToast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn(), dismiss: vi.fn() }))

vi.mock("@/lib/hooks/use-donors", () => ({
    useDonors: (filters: unknown) => mockUseDonors(filters),
}))

vi.mock("@/components/ui/toast", () => ({ toast: mockToast }))

vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ user: { user_id: "user-1" } }) }))
vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => ({
        data: { permissions: ["view_surrogates", "view_intended_parents", "view_donors"] },
    }),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSurrogates: () => ({ data: { items: [] }, isLoading: false }),
}))

vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParents: () => ({ data: { items: [] }, isLoading: false }),
}))

vi.mock("@/components/ui/select", () => ({
    Select: ({
        value,
        onValueChange,
        children,
    }: {
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

import { AddTaskDialog } from "@/components/tasks/AddTaskDialog"

function renderDialog(onSubmit = vi.fn().mockResolvedValue(undefined)) {
    const onOpenChange = vi.fn()
    render(
        <AddTaskDialog
            open
            onOpenChange={onOpenChange}
            onSubmit={onSubmit}
            isPending={false}
        />
    )
    return { onOpenChange, onSubmit }
}

describe("AddTaskDialog", () => {
    beforeEach(() => {
        Object.values(mockToast).forEach((fn) => fn.mockReset())
        mockUseDonors.mockImplementation((filters: { donor_type: string }) => ({
            data: {
                items: filters.donor_type === "egg"
                    ? [{
                        id: "donor-1",
                        donor_number: "D10001",
                        donor_type: "egg",
                        full_name: "Maya Thompson",
                    }]
                    : [],
            },
            isLoading: false,
        }))
    })

    it("requires a due date before creating recurring tasks", async () => {
        const { onSubmit } = renderDialog()

        fireEvent.change(screen.getByLabelText("Title *"), {
            target: { value: "Follow up" },
        })
        const repeatSelect = screen.getAllByRole("combobox")[1]!
        fireEvent.change(repeatSelect, { target: { value: "weekly" } })
        fireEvent.click(screen.getByRole("button", { name: "Create task" }))

        expect(await screen.findByText("Recurring tasks require a due date.")).toBeInTheDocument()
        expect(onSubmit).not.toHaveBeenCalled()
    })

    it("blocks a series longer than the occurrence limit instead of closing with nothing created", async () => {
        const { onSubmit, onOpenChange } = renderDialog()

        fireEvent.change(screen.getByLabelText("Title *"), { target: { value: "Daily check" } })
        fireEvent.change(screen.getByLabelText("Due Date"), { target: { value: "2026-01-01" } })
        fireEvent.change(screen.getAllByRole("combobox")[1]!, { target: { value: "daily" } })
        fireEvent.change(await screen.findByLabelText("Repeat Until"), { target: { value: "2026-12-31" } })
        fireEvent.click(screen.getByRole("button", { name: "Create task" }))

        expect(await screen.findByRole("alert")).toHaveTextContent("A repeating task can have at most 52 occurrences.")
        expect(onSubmit).not.toHaveBeenCalled()
        expect(onOpenChange).not.toHaveBeenCalled()
    })

    it("keeps the dialog open with a sanitized message when creation fails", async () => {
        const onSubmit = vi.fn().mockRejectedValue(new Error("SQL constraint task_owner_fk"))
        const { onOpenChange } = renderDialog(onSubmit)

        fireEvent.change(screen.getByLabelText("Title *"), { target: { value: "Follow up" } })
        fireEvent.click(screen.getByRole("button", { name: "Create task" }))

        expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't create task. Try again.")
        expect(screen.queryByText(/SQL constraint/)).not.toBeInTheDocument()
        expect(onOpenChange).not.toHaveBeenCalled()
        expect(mockToast.success).not.toHaveBeenCalled()
    })

    it("submits trimmed task data and closes after creation", async () => {
        const onSubmit = vi.fn().mockResolvedValue(undefined)
        const { onOpenChange } = renderDialog(onSubmit)

        fireEvent.change(screen.getByLabelText("Title *"), {
            target: { value: "  Review records  " },
        })
        fireEvent.change(screen.getByLabelText("Description"), {
            target: { value: "  Check the latest upload.  " },
        })
        fireEvent.change(screen.getByLabelText("Due Date"), {
            target: { value: "2026-08-12" },
        })
        fireEvent.change(screen.getByLabelText("Due Time"), {
            target: { value: "09:30" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Create task" }))

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
        expect(onSubmit).toHaveBeenCalledWith({
            title: "Review records",
            task_type: "other",
            recurrence: "none",
            description: "Check the latest upload.",
            due_date: "2026-08-12",
            due_time: "09:30",
            surrogate_id: null,
            intended_parent_id: null,
            donor_id: null,
        })
        expect(onOpenChange).toHaveBeenCalledWith(false)
        expect(mockToast.success).toHaveBeenCalledWith("Task created")
        expect(screen.queryByText("Create a new task for your list.")).not.toBeInTheDocument()
    })

    it("submits an egg donor selected as the linked record", async () => {
        const onSubmit = vi.fn().mockResolvedValue(undefined)
        renderDialog(onSubmit)

        fireEvent.change(screen.getByLabelText("Title *"), {
            target: { value: "Review donor profile" },
        })
        fireEvent.click(screen.getByRole("button", { name: /^Linked record/ }))
        fireEvent.click(screen.getByRole("button", { name: "Donors" }))
        expect(screen.getByText("Donors", { selector: "[data-slot=command-group-heading]" })).toBeInTheDocument()
        fireEvent.click(await screen.findByRole("option", { name: "Maya Thompson · Egg Donor D10001" }))
        fireEvent.click(screen.getByRole("button", { name: "Create task" }))

        await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({
                donor_id: "donor-1",
                surrogate_id: null,
                intended_parent_id: null,
            }),
        ))
    })
})
