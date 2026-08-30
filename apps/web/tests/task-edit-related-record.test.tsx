import type { ReactNode } from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

vi.mock("@/lib/hooks/use-donors", () => ({
    useDonors: () => ({ data: { items: [] }, isLoading: false }),
}))
vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSurrogates: () => ({ data: { items: [] }, isLoading: false }),
}))
vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParents: () => ({ data: { items: [] }, isLoading: false }),
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

describe("TaskEditModal related record", () => {
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

        const linkedRecord = screen.getAllByRole("combobox")[1]
        expect(linkedRecord).toHaveValue("donor:donor-1")
        expect(screen.getByRole("option", { name: "Egg Donor D10001" })).toBeInTheDocument()

        fireEvent.change(linkedRecord, { target: { value: "none" } })
        fireEvent.click(screen.getByRole("button", { name: "Save Changes" }))

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
